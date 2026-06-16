import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { StepShareModal } from './StepShareModal';
import { AppointmentSchedulerModal } from './AppointmentSchedulerModal';

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
}

/**
 * Drop-in single-row affordance for any step of any collaborative module.
 * Renders two pill buttons: "Share this step" + "Schedule A/V call".
 * Internally manages both modal visibilities.
 */
export const CollabBar: React.FC<CollabBarProps> = ({
  module, decisionId, stepId, stepLabel, partyId, partyLabel, fields, decisionTitle,
  hideShare = false, hideCall = false,
}) => {
  const [showShare, setShowShare] = useState(false);
  const [showCall, setShowCall] = useState(false);
  if (!decisionId) return null;
  return (
    <>
      <View style={s.row}>
        {!hideShare && (
          <TouchableOpacity testID="collab-share-btn" style={[s.btn, { borderColor: '#0EA5E9' }]} onPress={() => setShowShare(true)}>
            <Ionicons name="share-social" size={14} color="#0EA5E9" />
            <Text style={[s.btnText, { color: '#0EA5E9' }]}>Share this step</Text>
          </TouchableOpacity>
        )}
        {!hideCall && (
          <TouchableOpacity testID="collab-call-btn" style={[s.btn, { borderColor: '#10B981' }]} onPress={() => setShowCall(true)}>
            <Ionicons name="videocam" size={14} color="#10B981" />
            <Text style={[s.btnText, { color: '#10B981' }]}>Schedule call</Text>
          </TouchableOpacity>
        )}
      </View>
      <StepShareModal
        visible={showShare} onClose={() => setShowShare(false)}
        module={module} decisionId={decisionId} stepId={stepId} stepLabel={stepLabel}
        partyId={partyId} partyLabel={partyLabel} fields={fields || []}
      />
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
