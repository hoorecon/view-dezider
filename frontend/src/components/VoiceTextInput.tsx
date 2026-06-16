import React from 'react';
import {
  View,
  TextInput,
  TextInputProps,
  StyleSheet,
  StyleProp,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { VoiceInput } from './VoiceInput';

/**
 * VoiceTextInput
 * ──────────────
 * A drop-in replacement for `<TextInput>` that places a compact
 * voice-record mic chip on the RIGHT-HAND SIDE of the input.
 *
 * - For single-line inputs the mic sits vertically-centered.
 * - For multi-line inputs the mic anchors to the TOP-RIGHT so it
 *   doesn't grow with the textarea height.
 * - Skip this component for fields that should not be voiced
 *   (emails, mobile numbers, OTPs, structured tokens, etc.) — for
 *   those keep the regular `<TextInput>`.
 *
 * Endpoint dispatch is delegated to <VoiceInput>:
 *   - `module='eg-trap'` for session-bound EG inputs (default)
 *   - `module='eg-generic'` for session-less inputs (eg. Gratitude
 *     Journal entries in the Advisor card)
 *
 * The mic appends transcribed text to the existing value with a
 * single space separator, mirroring the pattern proven in eg-trap.
 */
interface VoiceTextInputProps extends Omit<TextInputProps, 'style'> {
  /** Current text value. */
  value: string;
  /** Setter (raw or wrapped — we always pass a fresh string). */
  onChangeText: (text: string) => void;
  /** TextInput style (e.g. `s.input` or `s.textArea`). */
  inputStyle?: StyleProp<TextStyle>;
  /** Outer row wrapper style override. */
  containerStyle?: StyleProp<ViewStyle>;
  /** Tint for the mic chip. */
  color?: string;
  /** Distinguishes which audio field this represents in the backend. */
  field: string;
  /** Session id (only used when `module='eg-trap'`). Pass '' for generic. */
  sessionId?: string;
  /** 'eg-trap' = session-bound (default). 'eg-generic' = session-less. */
  module?: 'eg-trap' | 'eg-generic';
  /** Disable the mic without disabling the input. */
  voiceDisabled?: boolean;
}

export const VoiceTextInput: React.FC<VoiceTextInputProps> = ({
  value,
  onChangeText,
  inputStyle,
  containerStyle,
  color = '#3B82F6',
  field,
  sessionId = '',
  module = 'eg-trap',
  voiceDisabled = false,
  multiline,
  ...rest
}) => {
  const handleTranscribed = (t: string) => {
    if (!t) return;
    onChangeText(value && value.length > 0 ? value + ' ' + t : t);
  };

  return (
    <View style={[styles.row, containerStyle]}>
      <TextInput
        {...rest}
        multiline={multiline}
        value={value}
        onChangeText={onChangeText}
        style={[styles.flexInput, inputStyle]}
      />
      <View style={multiline ? styles.micWrapTop : styles.micWrapMid}>
        <VoiceInput
          sessionId={sessionId}
          field={field}
          color={color}
          module={module}
          disabled={voiceDisabled}
          onTranscribed={handleTranscribed}
        />
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  flexInput: {
    flex: 1,
  },
  // Multiline → mic anchored to top so it doesn't grow with textarea
  micWrapTop: {
    paddingTop: 4,
  },
  // Single-line → mic vertically centered against ~44px input
  micWrapMid: {
    paddingTop: 6,
  },
});

export default VoiceTextInput;
