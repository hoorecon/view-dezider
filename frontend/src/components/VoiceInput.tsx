import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  useAudioRecorder,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from 'expo-audio';
import api from '../utils/api';
import { COLORS } from '../constants/colors';

interface VoiceInputProps {
  sessionId: string;
  field: string;
  onTranscribed: (text: string) => void;
  disabled?: boolean;
  color?: string;
}

export const VoiceInput: React.FC<VoiceInputProps> = ({
  sessionId,
  field,
  onTranscribed,
  disabled = false,
  color = '#F59E0B',
}) => {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const startRecording = async () => {
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        alert('Microphone permission is required for voice input.');
        return;
      }

      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
      });

      await recorder.prepareToRecordAsync();
      recorder.record();
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording:', err);
      alert('Failed to start recording. Please try again.');
    }
  };

  const stopRecording = async () => {
    setIsRecording(false);
    setIsTranscribing(true);

    try {
      await recorder.stop();
      const uri = recorder.uri;

      if (!uri) {
        alert('Recording failed. Please try again.');
        setIsTranscribing(false);
        return;
      }

      // Send to backend for transcription
      const formData = new FormData();

      if (Platform.OS === 'web') {
        const response = await fetch(uri);
        const blob = await response.blob();
        formData.append('audio', blob, 'recording.wav');
      } else {
        formData.append('audio', {
          uri: uri,
          type: 'audio/wav',
          name: 'recording.wav',
        } as any);
      }
      formData.append('field', field);

      const result = await api.post(
        `/emotional-gatekeeper/trap/${sessionId}/voice`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 30000,
        }
      );

      if (result.data?.transcribed_text) {
        onTranscribed(result.data.transcribed_text);
      } else {
        alert('Could not transcribe audio. Please try again or type your response.');
      }
    } catch (err: any) {
      console.error('Transcription error:', err);
      alert('Transcription failed. Please type your response instead.');
    } finally {
      setIsTranscribing(false);
    }
  };

  if (isTranscribing) {
    return (
      <View style={[styles.container, { borderColor: color }]}>
        <ActivityIndicator size="small" color={color} />
        <Text style={[styles.statusText, { color }]}>Transcribing...</Text>
      </View>
    );
  }

  return (
    <TouchableOpacity
      style={[
        styles.container,
        { borderColor: isRecording ? '#EF4444' : color },
        isRecording && styles.recording,
        disabled && styles.disabled,
      ]}
      onPress={isRecording ? stopRecording : startRecording}
      disabled={disabled}
      activeOpacity={0.7}
    >
      <Ionicons
        name={isRecording ? 'stop-circle' : 'mic'}
        size={20}
        color={isRecording ? '#EF4444' : color}
      />
      <Text style={[styles.label, { color: isRecording ? '#EF4444' : color }]}>
        {isRecording ? 'Tap to Stop' : 'Voice Input'}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 20,
    borderWidth: 1.5,
    backgroundColor: '#FFF',
  },
  recording: {
    backgroundColor: '#FEF2F2',
  },
  disabled: {
    opacity: 0.5,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
  },
});
