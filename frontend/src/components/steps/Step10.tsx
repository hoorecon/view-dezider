import React from 'react';
import { View, Text, TouchableOpacity, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import { TEPFI_ELEMENTS, TEPFI_LAYERS } from '../../utils/decisionHelpers';

export default function Step10() {
  const { decision, saveDecision, selectOption, calculateDynamicWorth, setCurrentStep, router } = useDecision();

  const optionsWithDynamicWorth = decision.options.map(option => ({
    ...option,
    dynamic_worth: calculateDynamicWorth(option).worth,
  }));
  const sortedOptions = [...optionsWithDynamicWorth].sort((a, b) => b.dynamic_worth - a.dynamic_worth);

  const mppsWorth = decision.mpps_projected_worth;
  const hasImprovements = (decision.mpps_improvements || []).some(i => i.improvement_plan || i.projected_percentage);

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 10: Final Decision</Text>
      <Text style={styles.stepDescription}>
        Select your final option based on Case-1 results and MPPS analysis.
      </Text>

      {sortedOptions.map((option, index) => {
        const isSelected = decision.chosen_option_id === option.id;
        const isMPPSTarget = decision.mpps_option_id === option.id;

        return (
          <Card
            key={option.id}
            style={[
              styles.resultCard,
              index === 0 && styles.resultCardBest,
              isSelected && { borderWidth: 2, borderColor: COLORS.success },
            ]}
          >
            <View style={styles.resultHeader}>
              <View style={styles.resultRank}>
                <Text style={styles.rankText}>#{index + 1}</Text>
              </View>
              <View style={styles.resultInfo}>
                <Text style={styles.resultName}>{option.name}</Text>
                <Text style={styles.resultWorth}>
                  Case-1 Worth: {option.dynamic_worth.toFixed(1)}%
                </Text>
                {isMPPSTarget && mppsWorth && (
                  <Text style={{ fontSize: 13, fontWeight: '600', color: '#16A34A' }}>
                    MPPS Worth: {mppsWorth.toFixed(1)}%
                  </Text>
                )}
              </View>
              {index === 0 && (
                <View style={styles.bestBadge}>
                  <Ionicons name="trophy" size={16} color={COLORS.warning} />
                  <Text style={styles.bestText}>Best</Text>
                </View>
              )}
            </View>

            {isSelected ? (
              <View style={styles.selectedBadge}>
                <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
                <Text style={styles.selectedText}>Selected ({decision.decision_case})</Text>
              </View>
            ) : (
              <View style={styles.selectButtons}>
                <TouchableOpacity
                  style={[styles.selectButton, { marginRight: 6 }]}
                  onPress={() => selectOption(option.id, 'obvious')}
                >
                  <Text style={styles.selectButtonText}>Case-1</Text>
                </TouchableOpacity>
                {hasImprovements && isMPPSTarget && (
                  <TouchableOpacity
                    style={[styles.selectButton, { backgroundColor: '#16A34A' }]}
                    onPress={() => selectOption(option.id, 'trial')}
                  >
                    <Text style={styles.selectButtonText}>MPPS</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={[styles.selectButton, { backgroundColor: COLORS.textMuted }]}
                  onPress={() => selectOption(option.id, 'unavoidable')}
                >
                  <Text style={styles.selectButtonText}>Unavoidable</Text>
                </TouchableOpacity>
              </View>
            )}
          </Card>
        );
      })}

      {/* MPPS Improvement Summary */}
      {hasImprovements && (
        <Card style={[styles.factorCard, { borderLeftWidth: 3, borderLeftColor: '#16A34A' }]}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 }}>
            MPPS Improvement Plans
          </Text>
          {(decision.mpps_improvements || [])
            .filter(i => i.improvement_plan)
            .map((imp) => {
              const factor = decision.factors.find(f => f.id === imp.factor_id);
              const te = TEPFI_ELEMENTS.find(t => t.key === imp.tepfi_element);
              const tl = TEPFI_LAYERS.find(t => t.key === imp.tepfi_layer);
              return (
                <View key={imp.factor_id} style={{ marginBottom: 8, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                    <Text style={{ fontSize: 13, fontWeight: '600', color: COLORS.textPrimary }}>{factor?.name || 'Unknown'}</Text>
                    {imp.original_percentage !== undefined && imp.projected_percentage !== undefined && (
                      <Text style={{ fontSize: 11, color: '#16A34A' }}>
                        {imp.original_percentage}% → {imp.projected_percentage}%
                      </Text>
                    )}
                  </View>
                  <Text style={{ fontSize: 12, color: COLORS.textSecondary }}>{imp.improvement_plan}</Text>
                  {(te || tl) && (
                    <View style={{ flexDirection: 'row', gap: 4, marginTop: 3 }}>
                      {te && (
                        <View style={{ paddingHorizontal: 6, paddingVertical: 1, borderRadius: 8, backgroundColor: te.color + '18' }}>
                          <Text style={{ fontSize: 10, color: te.color, fontWeight: '600' }}>{te.label}</Text>
                        </View>
                      )}
                      {tl && (
                        <View style={{ paddingHorizontal: 6, paddingVertical: 1, borderRadius: 8, backgroundColor: tl.color + '18' }}>
                          <Text style={{ fontSize: 10, color: tl.color, fontWeight: '600' }}>{tl.label}</Text>
                        </View>
                      )}
                    </View>
                  )}
                </View>
              );
            })}
        </Card>
      )}

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(9)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        {decision.chosen_option_id && (
          <View style={{ gap: 8 }}>
            <GradientButton
              title="Complete Decision"
              onPress={() => {
                saveDecision({ status: 'completed' });
                router.back();
              }}
              variant="accent"
              style={styles.nextButton}
            />
            <TouchableOpacity
              onPress={async () => {
                try {
                  const token = await AsyncStorage.getItem('session_token');
                  const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
                  const resp = await fetch(`${baseUrl}/api/decision-templates`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                    body: JSON.stringify({
                      name: decision.title,
                      life_area: decision.life_area || decision.folder || '',
                      decision_type: decision.decision_type || '',
                      description: decision.context,
                      factors: decision.factors,
                    }),
                  });
                  const data = await resp.json();
                  if (data.is_approved) {
                    Alert.alert('Saved', 'Template published successfully!');
                  } else {
                    Alert.alert('Submitted', 'Template submitted for admin review.');
                  }
                } catch (err) {
                  Alert.alert('Error', 'Failed to save template');
                }
              }}
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, backgroundColor: '#EDE9FE', borderRadius: 10, borderWidth: 1, borderColor: COLORS.primary }}
            >
              <Ionicons name="bookmark-outline" size={16} color={COLORS.primary} />
              <Text style={{ fontSize: 13, fontWeight: '600', color: COLORS.primary }}>Save as Template</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    </View>
  );
}
