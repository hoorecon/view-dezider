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
  /** Render only the speaker / notes icon — no surrounding pill / label.
   *  Use this when mirroring the mute control inline next to a banner /
   *  button so the user can pre-mute BEFORE the loader fires. */
  iconOnly?: boolean;
  style?: ViewStyle;
}

export const LoaderMusicChip: React.FC<Props> = ({ slot, enabled, readyLabel, iconOnly, style }) => {
  const { available, playing, muted, toggleMute } = useLoaderMusic(enabled, slot);
  if (!available) return null; // no audio uploaded AND no default fallback

  const iconName = muted
    ? 'volume-mute-outline'
    : (playing ? 'musical-notes' : 'musical-notes-outline');
  const iconColor = muted ? '#64748B' : '#7C3AED';

  if (iconOnly) {
    return (
      <TouchableOpacity
        testID={`loader-music-icon-${slot}`}
        onPress={toggleMute}
        activeOpacity={0.7}
        accessibilityLabel={muted ? 'Unmute loader music' : 'Mute loader music'}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        style={[
          {
            width: 28, height: 28, borderRadius: 14,
            alignItems: 'center', justifyContent: 'center',
            backgroundColor: muted ? '#F1F5F9' : '#FAF5FF',
            borderWidth: 1, borderColor: muted ? '#CBD5E1' : '#E9D5FF',
          },
          style,
        ]}>
        <Ionicons name={iconName} size={14} color={iconColor} />
      </TouchableOpacity>
    );
  }

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
      style={[s.chip, muted ? s.chipMuted : s.chipOn, style]}>
      <Ionicons name={iconName} size={11} color={iconColor} />
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
