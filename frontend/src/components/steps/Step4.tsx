import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import type { Factor } from '../../types/decision';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';
import { calculateRatingsFromOrder } from '../../utils/decisionHelpers';
import { useAiTouchpoint, useAiEstimate } from '../../utils/aiEstimates';

export default function Step4() {
  const { decision, moveFactorUp, moveFactorDown, setCurrentStep, saveDecision } = useDecision();
  const router = useRouter();
  const aiEnabled = useAiTouchpoint('tp_prioritize_factors');
  const aiEstimate = useAiEstimate('factor_prioritize');
  const [aiBusy, setAiBusy] = useState(false);
  const topLevel = decision.factors.filter(f => !f.parent_id);
  const primaryFactors = topLevel.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = topLevel.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);

  // "Prioritize with AI" — one metered LLM call ranks every top-level factor.
  // We apply the suggested order (preserving each factor's category) and
  // recalc ratings; the user can still tweak with the up/down arrows after.
  const handlePrioritizeWithAI = async () => {
    if (aiBusy) return;
    setAiBusy(true);
    try {
      const res = await api.post('/ai/prioritize-factors', { decision_id: decision.id });
      const ranked: { id: string; rank: number }[] = res.data?.factors || [];
      if (ranked.length === 0) {
        showAlert('No suggestion', 'AI could not prioritise this time. You can reorder manually with the arrows.');
        return;
      }
      const orderById = new Map(ranked.map(r => [r.id, r.rank]));
      const updated = decision.factors.map(f =>
        orderById.has(f.id) ? { ...f, order: orderById.get(f.id) as number } : f);
      const withRatings = calculateRatingsFromOrder(updated, (decision as any).rating_gap_multiplier || 1.0);
      await saveDecision({ factors: withRatings });
      showAlert('Factors prioritised', 'AI ordered your factors by importance. Review and fine-tune with the arrows, then continue.');
    } catch (e: any) {
      if (e?.response?.status === 402) {
        showAlert('Out of AI credits', e?.response?.data?.detail || 'Top up your AI Wallet to use AI prioritisation.', [
          { text: 'Not now', style: 'cancel' },
          { text: 'View wallet', onPress: () => router.push('/ai-wallet' as any) },
        ]);
      } else {
        showAlert('Could not prioritise', e?.response?.data?.detail || 'Please try again, or reorder manually.');
      }
    } finally {
      setAiBusy(false);
    }
  };

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

      {aiEnabled && topLevel.length >= 2 && (
        <>
          <TouchableOpacity
            testID="step4-prioritize-ai"
            onPress={handlePrioritizeWithAI}
            disabled={aiBusy}
            activeOpacity={0.85}
            accessibilityLabel="Prioritize factors with AI"
            style={{
              flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
              backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 13, paddingHorizontal: 16,
              marginBottom: 6, opacity: aiBusy ? 0.7 : 1,
              shadowColor: '#7C3AED', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.25, shadowRadius: 6, elevation: 3,
            }}
          >
            {aiBusy
              ? <ActivityIndicator size="small" color="#FFF" />
              : <Ionicons name="sparkles" size={18} color="#FFF" />}
            <Text style={{ color: '#FFF', fontSize: 15, fontWeight: '800' }}>
              {aiBusy ? 'Prioritising…' : 'Prioritize with AI'}
            </Text>
          </TouchableOpacity>
          <Text style={{ fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginBottom: 14, lineHeight: 16, paddingHorizontal: 8 }}>
            AI ranks your factors by importance for this decision{aiEstimate ? ` · uses ~${aiEstimate} AI credits` : ''}. You can fine-tune the order with the arrows afterwards.
          </Text>
        </>
      )}

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
