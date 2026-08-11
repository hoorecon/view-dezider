import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import LoaderMusicChip from '../LoaderMusicChip';

export default function Step8() {
  const { decision, calculateDynamicWorth, setCurrentStep } = useDecision();
  // Reveal soundtrack — play for the first ~25 s the user lands on Step 8,
  // then auto-stop. The chip stays interactive (mute / un-mute) for the
  // entire visit.
  const [revealEnabled, setRevealEnabled] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setRevealEnabled(false), 25000);
    return () => clearTimeout(t);
  }, []);

  const optionsWithDynamicWorth = decision.options.map(option => ({
    ...option,
    dynamic_worth: calculateDynamicWorth(option).worth,
  }));
  const sortedOptions = [...optionsWithDynamicWorth].sort((a, b) => b.dynamic_worth - a.dynamic_worth);

  // Wave 2 (#8b) — When a Deep-Import auto-rank ran for this decision, the
  // server persisted the curated top-N option ids on the decision so we can
  // mark each one with a "Top by AI" badge for the user.
  const topByAi = new Set<string>((decision as any)?.deep_import_top_n_ids || []);
  const hasAiTop = topByAi.size > 0;

  const isDeciderApp = (decision as any)?.decider_kind === 'app';
  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>{isDeciderApp ? 'Step 7: Case-1 Results' : 'Step 8: Case-1 Results'}</Text>
      <Text style={styles.stepDescription}>
        Options ranked by worth percentage. The highest worth option is the best as per Case-1 analysis.
      </Text>

      {hasAiTop && (
        <View
          testID="step8-ai-top-banner"
          style={{
            flexDirection: 'row', alignItems: 'center', gap: 8,
            paddingHorizontal: 12, paddingVertical: 10, marginBottom: 12,
            backgroundColor: '#FAF5FF', borderWidth: 1, borderColor: '#C4B5FD',
            borderRadius: 10,
          }}>
          <Ionicons name="sparkles" size={16} color="#7C3AED" />
          <Text style={{ flex: 1, fontSize: 12.5, color: '#4C1D95', fontWeight: '600', lineHeight: 17 }}>
            {topByAi.size} option{topByAi.size === 1 ? '' : 's'} highlighted below were auto-ranked by AI from the Deep-Import crawl (using your Step 5 weightages). The full list still shows for comparison.
          </Text>
          {/* Pre-mute icon — user can silence the upcoming reveal soundtrack
              BEFORE the chip below auto-plays. */}
          <LoaderMusicChip slot="results_reveal" enabled={false} iconOnly />
        </View>
      )}

      {sortedOptions.map((option, index) => {
        const isAiTop = topByAi.has(option.id);
        return (
          <Card key={option.id} style={[
            styles.resultCard,
            index === 0 && styles.resultCardBest,
            isAiTop && { borderLeftWidth: 4, borderLeftColor: '#7C3AED' },
          ]}>
            <View style={styles.resultHeader}>
              <View style={styles.resultRank}>
                <Text style={styles.rankText}>#{index + 1}</Text>
              </View>
              <View style={styles.resultInfo}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <Text style={styles.resultName}>{option.name}</Text>
                  {isAiTop && (
                    <View
                      testID={`step8-ai-top-badge-${option.id}`}
                      style={{
                        flexDirection: 'row', alignItems: 'center', gap: 3,
                        paddingHorizontal: 7, paddingVertical: 2,
                        backgroundColor: '#7C3AED', borderRadius: 10,
                      }}>
                      <Ionicons name="sparkles" size={10} color="#FFF" />
                      <Text style={{ fontSize: 9.5, fontWeight: '800', color: '#FFF', letterSpacing: 0.3 }}>
                        TOP BY AI
                      </Text>
                    </View>
                  )}
                </View>
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
        );
      })}

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
