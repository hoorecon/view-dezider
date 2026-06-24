import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import VoiceStepInput from '../../src/components/VoiceStepInput';
import ShareStepModal from '../../src/components/ShareStepModal';
import CLDViewer from '../../src/components/CLDViewer';
import ExpertCallModal from '../../src/components/ExpertCallModal';
import LinkedSourcePill from '../../src/components/decisions/LinkedSourcePill';
import ModuleStoreActions from '../../src/components/ModuleStoreActions';
import { deadlineCountdown, formatHorizon } from '../../src/utils/dateLocalize';
import { DecisionProvider, useDecision } from '../../src/context/DecisionContext';
import { styles } from '../../src/styles/decisionStyles';
import { calculateRatingsFromOrder } from '../../src/utils/decisionHelpers';
import { safeBack, goHome } from '../../src/utils/navigation';
import { useFeatureGate } from '../../src/utils/useFeatureGate';
import api from '../../src/utils/api';

// Step components
import Step2 from '../../src/components/steps/Step2';
import Step3 from '../../src/components/steps/Step3';
import Step4 from '../../src/components/steps/Step4';
import Step5 from '../../src/components/steps/Step5';
import Step6 from '../../src/components/steps/Step6';
import Step7 from '../../src/components/steps/Step7';
import Step8 from '../../src/components/steps/Step8';
import Step9 from '../../src/components/steps/Step9';
import Step10 from '../../src/components/steps/Step10';

function PRRDecisionDetailInner() {
  const router = useRouter();
  const {
    decision,
    loading,
    saving,
    currentStep,
    setCurrentStep,
    shareModalVisible,
    setShareModalVisible,
    handleUniversalVoiceCommand,
    fetchDecision,
    saveDecision,
    id,
  } = useDecision();

  const [showCLD, setShowCLD] = useState(false);
  const [showCallModal, setShowCallModal] = useState(false);
  const { isOn: isFeatureOn } = useFeatureGate();

  // Inline title editor — pencil icon toggles a TextInput in place of the
  // static title. Used heavily by the "Fresh Decision" path where the title
  // starts as a smart default (e.g. "Assets (Movable & Immovable) — 13 Jun
  // 2026, 16:22") and the user wants to overwrite it without leaving Step 2.
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const titleInputRef = useRef<TextInput>(null);

  const beginTitleEdit = () => {
    setTitleDraft(decision?.title || '');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.focus(), 60);
  };
  const commitTitleEdit = async () => {
    const next = titleDraft.trim();
    setEditingTitle(false);
    if (!next || next === decision?.title) return;
    try {
      await saveDecision({ title: next });
    } catch { /* saveDecision surfaces its own error UI */ }
  };
  const cancelTitleEdit = () => {
    setEditingTitle(false);
    setTitleDraft('');
  };

  // Reset the page scroll to the top whenever the step changes, so each step
  // (e.g. Step 7 'Assess Options') always opens from the top instead of
  // inheriting the previous step's scroll offset.
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [currentStep]);

  // Auto-refresh any "automatic" Dependent-Decision links once per decision
  // open, so a linked factor reflects the latest result of its source.
  const autoRefreshedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!decision?.id || autoRefreshedRef.current === decision.id) return;
    autoRefreshedRef.current = decision.id;
    api.post(`/decisions/${decision.id}/links/refresh-auto`)
      .then((r) => { if (r.data?.changes?.length) fetchDecision().catch(() => {}); })
      .catch(() => { /* best effort */ });
  }, [decision?.id]);

  // Honour ?step=N query param coming from SWOT→Decider conversion so we
  // always land on Step 2 instead of the persisted current_step.
  // Apply once per load so navigating between steps inside the page isn't
  // hijacked by the query param.
  const { step: stepParam } = useLocalSearchParams<{ step?: string }>();
  const appliedStepParamRef = useRef<string | null>(null);
  useEffect(() => {
    if (!decision) return;
    if (!stepParam) return;
    if (appliedStepParamRef.current === String(decision.id)) return;
    const n = parseInt(String(stepParam), 10);
    if (!Number.isNaN(n) && n >= 2 && n <= 10) {
      setCurrentStep(n);
      appliedStepParamRef.current = String(decision.id);
    }
  }, [decision, stepParam, setCurrentStep]);

  const handleCLDApply = (results: {
    classifications: { [factorId: string]: 'primary' | 'secondary' };
    priorities: { factorId: string; order: number }[];
    gapMultipliers: { [factorId: string]: number };
  }) => {
    if (!decision) return;
    let updatedFactors = (decision.factors || []).map(f => {
      const cls = results.classifications[f.id];
      const priority = results.priorities.find(p => p.factorId === f.id);
      const gapMult = results.gapMultipliers[f.id];
      return {
        ...f,
        ...(cls ? { category: cls } : {}),
        ...(priority !== undefined ? { order: priority.order } : {}),
        ...(gapMult !== undefined ? { gap_multiplier: gapMult } : {}),
      };
    });
    // Recalculate ratings based on new order and gaps
    updatedFactors = calculateRatingsFromOrder(updatedFactors, decision.rating_gap_multiplier || 1.0);
    saveDecision({ factors: updatedFactors });
  };

  const STEP_NAMES: { [key: number]: string } = {
    2: 'Define Factors',
    3: 'Classify Factors',
    4: 'Prioritize',
    5: 'Rate Importance',
    6: 'Define Options',
    7: 'Assess Options',
    8: 'Results',
    9: 'MPPS Analysis',
    10: 'Final Decision',
  };

  const renderStepIndicator = () => (
    <View style={styles.stepIndicator}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((step) => (
          <TouchableOpacity
            key={step}
            testID={`step-dot-${step}`}
            onPress={() => setCurrentStep(step)}
            style={[
              styles.stepDot,
              step <= currentStep && styles.stepDotActive,
              step === currentStep && styles.stepDotCurrent,
            ]}
          >
            <Text style={[styles.stepDotText, step <= currentStep && styles.stepDotTextActive]}>
              {step}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {saving && <ActivityIndicator size="small" color={COLORS.primary} style={styles.savingIndicator} />}
      {/* CLD button - visible on Steps 3, 4, 5 */}
      {[3, 4, 5].includes(currentStep) && (
        <TouchableOpacity
          style={[styles.shareStepBtn, { marginRight: 4, backgroundColor: '#F5F3FF' }]}
          onPress={() => setShowCLD(true)}
        >
          <Ionicons name="git-network-outline" size={16} color={COLORS.primary} />
        </TouchableOpacity>
      )}
      {/* Call Expert button */}
      {isFeatureOn('collab_expert_call') && (
      <TouchableOpacity
        style={[styles.shareStepBtn, { marginRight: 4, backgroundColor: '#DCFCE7' }]}
        onPress={() => setShowCallModal(true)}
      >
        <Ionicons name="videocam-outline" size={16} color="#16A34A" />
      </TouchableOpacity>
      )}
      {currentStep >= 2 && currentStep <= 9 && isFeatureOn('collab_share') && (
        <TouchableOpacity
          style={styles.shareStepBtn}
          onPress={() => setShareModalVisible(true)}
        >
          <Ionicons name="share-outline" size={18} color={COLORS.primary} />
        </TouchableOpacity>
      )}
    </View>
  );

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 2: return <Step2 />;
      case 3: return <Step3 />;
      case 4: return <Step4 />;
      case 5: return <Step5 />;
      case 6: return <Step6 />;
      case 7: return <Step7 />;
      case 8: return <Step8 />;
      case 9: return <Step9 />;
      case 10: return <Step10 />;
      default: return <Step2 />;
    }
  };

  if (loading || !decision) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <View style={styles.titleSection}>
          <TouchableOpacity
            onPress={() => safeBack(router)}
            style={{ width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginRight: 6 }}
            accessibilityLabel="Back"
          >
            <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
          </TouchableOpacity>
          {editingTitle ? (
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <TextInput
                ref={titleInputRef}
                value={titleDraft}
                onChangeText={setTitleDraft}
                onSubmitEditing={commitTitleEdit}
                onBlur={commitTitleEdit}
                returnKeyType="done"
                maxLength={120}
                testID="prr-title-input"
                style={[styles.decisionTitle, {
                  borderWidth: 1, borderColor: COLORS.primary, borderRadius: 8,
                  paddingHorizontal: 8, paddingVertical: 4,
                  backgroundColor: '#FFF',
                }]}
              />
              <TouchableOpacity
                onPress={commitTitleEdit}
                testID="prr-title-save"
                style={{ paddingHorizontal: 6, paddingVertical: 4 }}
                accessibilityLabel="Save title"
              >
                <Ionicons name="checkmark" size={22} color={COLORS.primary} />
              </TouchableOpacity>
              <TouchableOpacity
                onPress={cancelTitleEdit}
                testID="prr-title-cancel"
                style={{ paddingHorizontal: 6, paddingVertical: 4 }}
                accessibilityLabel="Cancel title edit"
              >
                <Ionicons name="close" size={20} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity
              onPress={beginTitleEdit}
              style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}
              testID="prr-title-edit"
              accessibilityLabel="Edit decision title"
            >
              <Text style={styles.decisionTitle} numberOfLines={1}>{decision.title}</Text>
              <Ionicons name="pencil" size={14} color={COLORS.textSecondary} />
            </TouchableOpacity>
          )}
          <View style={styles.headerStatusBadge}>
            <Text style={styles.headerStatusText}>
              Step {currentStep}/10
            </Text>
          </View>
          <TouchableOpacity
            onPress={() => goHome(router)}
            style={{ width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginLeft: 6 }}
            accessibilityLabel="Home"
          >
            <Ionicons name="home-outline" size={19} color={COLORS.textPrimary} />
          </TouchableOpacity>
        </View>
        {/* Timing context banner (Enhancement #4) */}
        {(decision.deadline_date || decision.impact_horizon_value || decision.linked_from_decision_id) && (() => {
          const cd = deadlineCountdown(decision.deadline_date);
          return (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingHorizontal: 16, paddingVertical: 6, backgroundColor: '#F8FAFC', borderBottomWidth: 1, borderBottomColor: COLORS.divider }}>
              {cd ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, backgroundColor: cd.severity === 'overdue' ? '#FEE2E2' : cd.severity === 'danger' ? '#FED7AA' : cd.severity === 'warn' ? '#FEF3C7' : '#E0F2FE' }}>
                  <Ionicons name="time-outline" size={11} color={cd.severity === 'overdue' ? '#B91C1C' : cd.severity === 'danger' ? '#9A3412' : cd.severity === 'warn' ? '#92400E' : '#075985'} />
                  <Text style={{ fontSize: 11, fontWeight: '700', color: cd.severity === 'overdue' ? '#B91C1C' : cd.severity === 'danger' ? '#9A3412' : cd.severity === 'warn' ? '#92400E' : '#075985' }}>deadline {cd.text}</Text>
                </View>
              ) : null}
              {decision.impact_horizon_value ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, backgroundColor: '#F3E8FF' }}>
                  <Ionicons name="hourglass-outline" size={11} color="#7C3AED" />
                  <Text style={{ fontSize: 11, fontWeight: '700', color: '#7C3AED' }}>impact {formatHorizon(decision.impact_horizon_value, decision.impact_horizon_unit)}</Text>
                </View>
              ) : null}
              {decision.linked_from_decision_id ? (
                <LinkedSourcePill
                  decision_id={decision.linked_from_decision_id}
                  module={decision.linked_from_module}
                  option_label={decision.linked_from_option_label}
                  score_pct={decision.linked_from_score_pct ?? undefined}
                  compact
                />
              ) : null}
            </View>
          );
        })()}
        {renderStepIndicator()}
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {renderCurrentStep()}
          <ModuleStoreActions
            module="dezider"
            decisionId={id || ''}
            lifeAreaId={(decision as any)?.life_area_id || decision?.life_area || null}
            subAreaId={(decision as any)?.sub_area_id || null}
          />
        </ScrollView>
        {/* Universal voice input panel */}
        {currentStep !== 5 && (
          <VoiceStepInput
            step={currentStep}
            factors={decision.factors || []}
            options={(decision.options || []).map(o => ({ id: o.id, name: o.name }))}
            onCommand={handleUniversalVoiceCommand}
          />
        )}
      </KeyboardAvoidingView>

      {/* Share Step Modal */}
      <ShareStepModal
        visible={shareModalVisible}
        onClose={() => setShareModalVisible(false)}
        decisionId={id}
        stepNumber={currentStep}
        stepName={STEP_NAMES[currentStep] || `Step ${currentStep}`}
        onShareSuccess={() => { fetchDecision(); }}
      />

      {/* CLD Viewer */}
      <CLDViewer
        visible={showCLD}
        onClose={() => setShowCLD(false)}
        factors={decision.factors}
        decisionId={id}
        decisionTitle={decision.title}
        decisionContext={decision.context}
        lifeArea={decision.life_area}
        decisionType={decision.decision_type}
        onApplyResults={handleCLDApply}
      />

      {/* Expert Call Modal */}
      <ExpertCallModal
        visible={showCallModal}
        onClose={() => setShowCallModal(false)}
        decisionId={id}
        decisionTitle={decision.title}
        stepNumber={currentStep}
        stepName={STEP_NAMES[currentStep] || `Step ${currentStep}`}
      />
    </SafeAreaView>
  );
}

export default function PRRDecisionDetail() {
  return (
    <DecisionProvider>
      <PRRDecisionDetailInner />
    </DecisionProvider>
  );
}
