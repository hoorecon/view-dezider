import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Alert, TextInput, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import ActionItemEditor from '../ActionItemEditor';
import { styles } from '../../styles/decisionStyles';
import { TEPFI_ELEMENTS, TEPFI_LAYERS } from '../../utils/decisionHelpers';
import { showAlert } from '../../utils/alert';

export default function Step10() {
  const { decision, saveDecision, selectOption, calculateDynamicWorth, setCurrentStep, router } = useDecision();
  const [reviewDateStr, setReviewDateStr] = useState(
    decision.implementation_review_date
      ? new Date(decision.implementation_review_date).toISOString().split('T')[0]
      : ''
  );
  const [reasonStr, setReasonStr] = useState(decision.final_choice_reason || '');
  // Auto-push MPPS improvement plans into the Action Plan when this step opens.
  const [mppsReady, setMppsReady] = useState(false);
  const [actionRefreshKey, setActionRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const imps = (decision as any).mpps_improvements || [];
      if (!imps.length) { if (!cancelled) setMppsReady(true); return; }
      try {
        const token = await AsyncStorage.getItem('session_token');
        const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
        await fetch(`${baseUrl}/api/action-items/import-from-mpps/${decision.id}`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        });
      } catch { /* non-fatal — manual add still works */ }
      if (!cancelled) { setMppsReady(true); setActionRefreshKey((k) => k + 1); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decision.id]);

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

      {/* Why I chose this — reason (parity with Pros & Cons) */}
      {decision.chosen_option_id && (
        <Card style={[styles.factorCard, { borderLeftWidth: 3, borderLeftColor: COLORS.success }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Ionicons name="create-outline" size={16} color={COLORS.success} />
            <Text style={{ fontSize: 14, fontWeight: '700', color: COLORS.textPrimary }}>Why I chose this</Text>
          </View>
          <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginBottom: 8 }}>
            Capture your reasoning for this final choice — it appears in the PDF report.
          </Text>
          <TextInput
            style={{
              backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1,
              borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 10,
              fontSize: 15, color: COLORS.textPrimary, minHeight: 84, textAlignVertical: 'top',
            }}
            placeholder="e.g., Best balance of cost and long-term growth…"
            value={reasonStr}
            onChangeText={setReasonStr}
            onBlur={() => { if (reasonStr !== (decision.final_choice_reason || '')) saveDecision({ final_choice_reason: reasonStr }); }}
            multiline
            placeholderTextColor={COLORS.textMuted}
          />
        </Card>
      )}

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

      {/* Implementation Review Date & Journal */}
      <Card style={[styles.factorCard, { borderLeftWidth: 3, borderLeftColor: '#F59E0B' }]}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 }}>
          <Ionicons name="calendar" size={16} color="#F59E0B" />
          <Text style={{ fontSize: 14, fontWeight: '700', color: COLORS.textPrimary }}>
            Implementation Review Date
          </Text>
        </View>
        <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginBottom: 8 }}>
          Set a date to review this decision&#39;s outcome and document learnings
        </Text>
        <TextInput
          style={{
            backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1,
            borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 10,
            fontSize: 15, color: COLORS.textPrimary,
          }}
          placeholder="YYYY-MM-DD (e.g., 2026-06-15)"
          value={reviewDateStr}
          onChangeText={(text) => {
            setReviewDateStr(text);
            // Auto-save when valid date format
            if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
              const d = new Date(text + 'T00:00:00Z');
              if (!isNaN(d.getTime())) {
                saveDecision({ implementation_review_date: d.toISOString() });
              }
            }
          }}
          placeholderTextColor={COLORS.textMuted}
        />
        {decision.decision_type && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }}>
            <View style={{
              paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
              backgroundColor: decision.decision_type === 'problem' ? '#EF444418' : decision.decision_type === 'need' ? '#F59E0B18' : '#10B98118',
            }}>
              <Text style={{
                fontSize: 11, fontWeight: '700',
                color: decision.decision_type === 'problem' ? '#EF4444' : decision.decision_type === 'need' ? '#F59E0B' : '#10B981',
              }}>
                {decision.decision_type === 'problem' ? 'P0 — Critical' : decision.decision_type === 'need' ? 'P1 — Important' : 'P2 — Aspiration'}
              </Text>
            </View>
            {(decision.decision_type === 'problem' || decision.decision_type === 'need') && (
              <Text style={{ fontSize: 11, color: '#B91C1C' }}>
                Auto-reminder will appear on review date
              </Text>
            )}
          </View>
        )}
      </Card>

      {/* Action Plan — MPPS improvement plans auto-pushed here + manual adds.
          Flows to Action Center / CTT / Lifestyle. */}
      {mppsReady && (
        <View style={{ marginTop: 4 }}>
          <ActionItemEditor
            key={actionRefreshKey}
            sourceModule="MYDEZIDER_MPPS"
            sourceId={decision.id}
            sourceLabel={`My Dezider · ${decision.title || ''}`}
            defaultLifeArea={decision.life_area || decision.folder || ''}
            title="Action Plan — Who · What · By When"
          />
        </View>
      )}

      {/* Document Learnings button (for completed decisions) */}
      {decision.status === 'completed' && (
        <TouchableOpacity
          onPress={() => {
            router.push({
              pathname: '/(tabs)/journal',
              params: { linkModule: 'decision', linkId: decision.id, linkTitle: decision.title },
            });
          }}
          style={{
            flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
            paddingVertical: 14, backgroundColor: '#10B98115', borderRadius: 12,
            borderWidth: 1.5, borderColor: '#10B981', marginTop: 4,
          }}
        >
          <Ionicons name="book" size={18} color="#10B981" />
          <Text style={{ fontSize: 14, fontWeight: '700', color: '#10B981' }}>
            Document Learnings
          </Text>
        </TouchableOpacity>
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
                showAlert(
                  'Complete this decision?',
                  'This marks the decision as Completed. You can still review or edit it later.',
                  [
                    { text: 'Not yet', style: 'cancel' },
                    {
                      text: 'Complete',
                      onPress: async () => {
                        try {
                          await saveDecision({
                            status: 'completed',
                            final_choice_reason: reasonStr || undefined,
                            final_choice_decided_at: decision.final_choice_decided_at || new Date().toISOString(),
                          });
                          showAlert('Decision Completed 🎉', 'Your decision has been marked as completed.', [
                            { text: 'Done', onPress: () => { if (router.canGoBack?.()) router.back(); else router.replace('/(tabs)' as any); } },
                          ]);
                        } catch (e) {
                          showAlert('Could not complete', 'Something went wrong. Please try again.');
                        }
                      },
                    },
                  ]
                );
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
