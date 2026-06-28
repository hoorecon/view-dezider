import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { StepShareModal } from './StepShareModal';
import ShareStepModal from './ShareStepModal';
import { AppointmentSchedulerModal } from './AppointmentSchedulerModal';
import { useFeatureGate } from '../utils/useFeatureGate';

interface CollabBarProps {
  module: 'conflict-breaker' | 'pros-cons' | 'swot' | 'solution-finder' | 'goal-setter' | 'my-dezider';
  decisionId: string;
  stepId: string;
  stepLabel: string;
  partyId?: string;
  partyLabel?: string;
  fields?: string[];
  decisionTitle?: string;
  /** Hide one of the buttons if not applicable. */
  hideShare?: boolean;
  hideCall?: boolean;
  /** Use the share-step system (real-flow clone + Review & Merge + AI Auto-Merge)
   *  instead of the WhatsApp invite. Set for Pros&Cons / SWOT / Solution Finder. */
  useShareStep?: boolean;
  /** Numeric step index for the share-step system. */
  stepNumber?: number;
}

/**
 * Drop-in single-row affordance for any step of any collaborative module.
 * Renders pill buttons: "Share this step" + (owner) "Review & merge" + "Schedule call".
 * Internally manages all modal visibilities.
 */
export const CollabBar: React.FC<CollabBarProps> = ({
  module, decisionId, stepId, stepLabel, partyId, partyLabel, fields, decisionTitle,
  hideShare = false, hideCall = false, useShareStep = false, stepNumber,
}) => {
  const [showShare, setShowShare] = useState(false);
  const [showCall, setShowCall] = useState(false);
  const [showShareStep, setShowShareStep] = useState(false);
  const [shareStepSent, setShareStepSent] = useState(false);
  const { isOn } = useFeatureGate();
  if (!decisionId) return null;
  // Combine caller's prop with the central ACM toggle (Collaboration module).
  const showShareBtn = !hideShare && isOn('collab_share');
  const showCallBtn = !hideCall && isOn('collab_expert_call');
  const openShareStep = (sent: boolean) => { setShareStepSent(sent); setShowShareStep(true); };
  return (
    <>
      <View style={s.row}>
        {showShareBtn && (
          <TouchableOpacity
            testID="collab-share-btn" style={[s.btn, { borderColor: '#0EA5E9' }]}
            onPress={() => (useShareStep ? openShareStep(false) : setShowShare(true))}
          >
            <Ionicons name="share-social" size={14} color="#0EA5E9" />
            <Text style={[s.btnText, { color: '#0EA5E9' }]}>Share this step</Text>
          </TouchableOpacity>
        )}
        {showShareBtn && useShareStep && (
          <TouchableOpacity
            testID="collab-review-btn" style={[s.btn, { borderColor: '#7C3AED' }]}
            onPress={() => openShareStep(true)}
          >
            <Ionicons name="git-compare" size={14} color="#7C3AED" />
            <Text style={[s.btnText, { color: '#7C3AED' }]}>Review &amp; merge</Text>
          </TouchableOpacity>
        )}
        {showCallBtn && (
          <TouchableOpacity testID="collab-call-btn" style={[s.btn, { borderColor: '#10B981' }]} onPress={() => setShowCall(true)}>
            <Ionicons name="videocam" size={14} color="#10B981" />
            <Text style={[s.btnText, { color: '#10B981' }]}>Schedule call</Text>
          </TouchableOpacity>
        )}
      </View>
      {!useShareStep && (
        <StepShareModal
          visible={showShare} onClose={() => setShowShare(false)}
          module={module} decisionId={decisionId} stepId={stepId} stepLabel={stepLabel}
          partyId={partyId} partyLabel={partyLabel} fields={fields || []}
        />
      )}
      {useShareStep && (
        <ShareStepModal
          visible={showShareStep}
          onClose={() => setShowShareStep(false)}
          decisionId={decisionId}
          stepNumber={stepNumber ?? 1}
          stepName={stepLabel}
          module={module}
          initialShowSent={shareStepSent}
          onShareSuccess={() => {}}
        />
      )}
      <AppointmentSchedulerModal
        visible={showCall} onClose={() => setShowCall(false)}
        module={module} decisionId={decisionId} stepId={stepId}
        defaultTitle={`${decisionTitle || stepLabel} — discussion`}
      />
    </>
  );
};

const s = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1.2, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#FFFFFF' },
  btnText: { fontSize: 12, fontWeight: '700' },
});

export default CollabBar;
