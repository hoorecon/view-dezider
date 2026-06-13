/**
 * LoaderMusicChip — reusable "loader music + mute toggle" chip.
 *
 * Drop into any long-running progress UI:
 *
 *   <LoaderMusicChip slot="ai_assess_all" enabled={bulkAssessing} />
 *
 * The chip auto-hides when no audio is available for the slot (and no
 * default fallback either), so any progress UI can include it
 * unconditionally without worrying about empty admin slots cluttering
 * the screen.
 *
 * Three visual states:
 *   ▶ playing    — purple "musical-notes" icon, "tap to mute" hint
 *   ⏸ ready      — purple outlined icon, "tap to mute"
 *   🔇 muted     — grey `volume-mute-outline`, "tap to unmute"
 *
 * Per-user mute is GLOBAL across slots (one AsyncStorage key) so flipping
 * mute on the AI-Assess-All chip also silences the Deep-Import chip.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLoaderMusic, LoaderSlot } from '../hooks/useLoaderMusic';

interface Props {
  slot: LoaderSlot;
  enabled: boolean;
  /** Override the label shown when audio is *ready but not playing*. */
  readyLabel?: string;
  style?: ViewStyle;
}

export const LoaderMusicChip: React.FC<Props> = ({ slot, enabled, readyLabel, style }) => {
  const { available, playing, muted, toggleMute } = useLoaderMusic(enabled, slot);
  if (!available) return null; // no audio uploaded AND no default fallback

  const label = muted
    ? 'Music muted — tap to unmute'
    : playing
      ? 'Loader music playing — tap to mute'
      : (readyLabel || 'Loader music ready — tap to mute');
  return (
    <TouchableOpacity
      testID={`loader-music-chip-${slot}`}
      onPress={toggleMute}
      activeOpacity={0.7}
      style={[
        s.chip,
        muted ? s.chipMuted : s.chipOn,
        style,
      ]}>
      <Ionicons
        name={muted ? 'volume-mute-outline' : (playing ? 'musical-notes' : 'musical-notes-outline')}
        size={11}
        color={muted ? '#64748B' : '#7C3AED'}
      />
      <Text style={[s.txt, muted && { color: '#64748B' }]}>{label}</Text>
    </TouchableOpacity>
  );
};

export default LoaderMusicChip;

const s = StyleSheet.create({
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'flex-start',
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 14, borderWidth: 1,
  },
  chipOn: { backgroundColor: '#FAF5FF', borderColor: '#E9D5FF' },
  chipMuted: { backgroundColor: '#F1F5F9', borderColor: '#CBD5E1' },
  txt: { fontSize: 10.5, fontWeight: '700', color: '#7C3AED' },
});
