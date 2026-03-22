import React from 'react';
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
import { DecisionProvider, useDecision } from '../../src/context/DecisionContext';
import { styles } from '../../src/styles/decisionStyles';

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
    id,
  } = useDecision();

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
        stepName={`Step ${currentStep}`}
        onShareSuccess={() => { fetchDecision(); }}
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
