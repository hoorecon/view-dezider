import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import VoiceStepInput from '../../src/components/VoiceStepInput';
import ShareStepModal from '../../src/components/ShareStepModal';
import CLDViewer from '../../src/components/CLDViewer';
import ExpertCallModal from '../../src/components/ExpertCallModal';
import { DecisionProvider, useDecision } from '../../src/context/DecisionContext';
import { styles } from '../../src/styles/decisionStyles';
import { calculateRatingsFromOrder } from '../../src/utils/decisionHelpers';

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

  const handleCLDApply = (results: {
    classifications: { [factorId: string]: 'primary' | 'secondary' };
    priorities: { factorId: string; order: number }[];
    gapMultipliers: { [factorId: string]: number };
  }) => {
    if (!decision) return;
    let updatedFactors = decision.factors.map(f => {
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
      <TouchableOpacity
        style={[styles.shareStepBtn, { marginRight: 4, backgroundColor: '#DCFCE7' }]}
        onPress={() => setShowCallModal(true)}
      >
        <Ionicons name="videocam-outline" size={16} color="#16A34A" />
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.shareStepBtn}
        onPress={() => setShareModalVisible(true)}
      >
        <Ionicons name="share-outline" size={18} color={COLORS.primary} />
      </TouchableOpacity>
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
          <Text style={styles.decisionTitle} numberOfLines={1}>{decision.title}</Text>
          <View style={styles.headerStatusBadge}>
            <Text style={styles.headerStatusText}>
              Step {currentStep}/10
            </Text>
          </View>
        </View>
        {renderStepIndicator()}
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {renderCurrentStep()}
        </ScrollView>
        {/* Universal voice input panel */}
        {currentStep !== 5 && (
          <VoiceStepInput
            step={currentStep}
            factors={decision.factors}
            options={decision.options.map(o => ({ id: o.id, name: o.name }))}
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
