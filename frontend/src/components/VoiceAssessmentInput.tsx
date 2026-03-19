import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Platform,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { parseVoiceCommand, describeCommand, ParsedVoiceCommand } from '../utils/voiceCommandParser';

// Conditional import for speech recognition - works on web and native dev client
let ExpoSpeechRecognitionModule: any = null;
let useSpeechRecognitionEvent: any = null;

try {
  const speechModule = require('expo-speech-recognition');
  ExpoSpeechRecognitionModule = speechModule.ExpoSpeechRecognitionModule;
  useSpeechRecognitionEvent = speechModule.useSpeechRecognitionEvent;
} catch (e) {
  console.log('Speech recognition module not available');
}

interface Factor {
  id: string;
  name: string;
  rating: number;
}

interface VoiceAssessmentInputProps {
  factors: Factor[];
  onCommand: (command: ParsedVoiceCommand) => void;
  disabled?: boolean;
}

// Animated pulse ring component
function PulseRing({ isActive }: { isActive: boolean }) {
  const scale = useRef(new Animated.Value(1)).current;
  const opacity = useRef(new Animated.Value(0.6)).current;

  useEffect(() => {
    if (isActive) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.parallel([
            Animated.timing(scale, { toValue: 1.8, duration: 1000, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 0, duration: 1000, useNativeDriver: true }),
          ]),
          Animated.parallel([
            Animated.timing(scale, { toValue: 1, duration: 0, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 0.6, duration: 0, useNativeDriver: true }),
          ]),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    } else {
      scale.setValue(1);
      opacity.setValue(0.6);
    }
  }, [isActive]);

  if (!isActive) return null;

  return (
    <Animated.View
      style={[
        styles.pulseRing,
        { transform: [{ scale }], opacity },
      ]}
    />
  );
}

export default function VoiceAssessmentInput({ factors, onCommand, disabled }: VoiceAssessmentInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [lastCommand, setLastCommand] = useState<ParsedVoiceCommand | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState('');
  const [isAvailable, setIsAvailable] = useState(false);
  const [commandHistory, setCommandHistory] = useState<Array<{ text: string; success: boolean }>>([]);
  
  const micScale = useRef(new Animated.Value(1)).current;

  // Check availability on mount
  useEffect(() => {
    checkAvailability();
  }, []);

  const checkAvailability = async () => {
    if (!ExpoSpeechRecognitionModule) {
      setIsAvailable(false);
      return;
    }
    try {
      // Check if the browser/device supports speech recognition
      if (Platform.OS === 'web') {
        const supported = typeof window !== 'undefined' && 
          ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
        setIsAvailable(supported);
      } else {
        setIsAvailable(true);
      }
    } catch {
      setIsAvailable(false);
    }
  };

  // Set up speech recognition event handlers
  if (useSpeechRecognitionEvent) {
    useSpeechRecognitionEvent('start', () => {
      setIsListening(true);
      setTranscript('');
      setError('');
    });

    useSpeechRecognitionEvent('end', () => {
      setIsListening(false);
    });

    useSpeechRecognitionEvent('result', (event: any) => {
      const result = event.results?.[event.results.length - 1];
      if (result?.transcript) {
        setTranscript(result.transcript);
        
        // If it's a final result, parse it
        if (result.isFinal || !event.results?.some?.((r: any) => !r.isFinal)) {
          processTranscript(result.transcript);
        }
      }
    });

    useSpeechRecognitionEvent('error', (event: any) => {
      console.log('Speech error:', event.error, event.message);
      setIsListening(false);
      if (event.error === 'no-speech') {
        setError('No speech detected. Tap mic and speak clearly.');
      } else if (event.error === 'not-allowed') {
        setError('Microphone permission denied. Please allow access.');
      } else {
        setError(`Error: ${event.message || event.error || 'Recognition failed'}`);
      }
    });
  }

  const processTranscript = useCallback((text: string) => {
    const command = parseVoiceCommand(text, factors);
    
    if (command && command.confidence >= 0.4 && (command.factorId || command.allFactors)) {
      setLastCommand(command);
      onCommand(command);
      setCommandHistory(prev => [
        { text: describeCommand(command), success: true },
        ...prev.slice(0, 4),
      ]);
    } else {
      setCommandHistory(prev => [
        { text: `"${text}" — Not recognized`, success: false },
        ...prev.slice(0, 4),
      ]);
    }
  }, [factors, onCommand]);

  const startListening = async () => {
    if (!ExpoSpeechRecognitionModule || !isAvailable) {
      setError('Voice input is not available on this device/browser');
      return;
    }

    setError('');
    setTranscript('');
    setLastCommand(null);
    setShowModal(true);

    try {
      const { granted } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!granted) {
        setError('Microphone permission is required for voice input');
        return;
      }

      await ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        continuous: false,
        maxAlternatives: 1,
        addsPunctuation: false,
        contextualStrings: [
          ...factors.map(f => f.name),
          'high', 'medium', 'low', 'percent',
          'all', 'every',
        ],
      });

      // Animate mic press
      Animated.spring(micScale, {
        toValue: 0.9,
        useNativeDriver: true,
      }).start();
    } catch (err: any) {
      console.error('Start error:', err);
      setError(err.message || 'Failed to start voice input');
    }
  };

  const stopListening = async () => {
    if (ExpoSpeechRecognitionModule) {
      try {
        await ExpoSpeechRecognitionModule.stop();
      } catch (e) {
        // ignore
      }
    }
    setIsListening(false);
    Animated.spring(micScale, {
      toValue: 1,
      useNativeDriver: true,
    }).start();
  };

  const closeModal = () => {
    stopListening();
    setShowModal(false);
    setTranscript('');
    setError('');
  };

  if (!isAvailable && !ExpoSpeechRecognitionModule) {
    return null; // Don't render if not available
  }

  return (
    <>
      {/* Floating Mic Button */}
      <TouchableOpacity
        style={[styles.micButton, disabled && styles.micButtonDisabled]}
        onPress={() => {
          if (isListening) {
            stopListening();
          } else {
            startListening();
          }
        }}
        disabled={disabled}
        activeOpacity={0.7}
      >
        <View style={styles.micButtonInner}>
          <Ionicons
            name={isListening ? 'mic' : 'mic-outline'}
            size={20}
            color={isListening ? '#FFFFFF' : COLORS.primary}
          />
          <Text style={[styles.micButtonText, isListening && styles.micButtonTextActive]}>
            {isListening ? 'Listening...' : 'Voice Input'}
          </Text>
        </View>
      </TouchableOpacity>

      {/* Voice Input Modal */}
      <Modal
        visible={showModal}
        transparent
        animationType="slide"
        onRequestClose={closeModal}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {/* Header */}
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Voice Assessment</Text>
              <TouchableOpacity onPress={closeModal} style={styles.closeButton}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>

            {/* Instructions */}
            <View style={styles.instructions}>
              <Text style={styles.instructionTitle}>Say a command like:</Text>
              <Text style={styles.instructionExample}>"Decision Power High"</Text>
              <Text style={styles.instructionExample}>"Timeline 60 percent"</Text>
              <Text style={styles.instructionExample}>"All Medium"</Text>
            </View>

            {/* Mic Area */}
            <View style={styles.micArea}>
              <PulseRing isActive={isListening} />
              <Animated.View style={{ transform: [{ scale: micScale }] }}>
                <TouchableOpacity
                  style={[
                    styles.bigMicButton,
                    isListening && styles.bigMicButtonActive,
                  ]}
                  onPress={() => {
                    if (isListening) {
                      stopListening();
                    } else {
                      startListening();
                    }
                  }}
                  activeOpacity={0.8}
                >
                  <Ionicons
                    name={isListening ? 'mic' : 'mic-outline'}
                    size={40}
                    color="#FFFFFF"
                  />
                </TouchableOpacity>
              </Animated.View>
              <Text style={styles.micStatus}>
                {isListening ? 'Listening... Speak now' : 'Tap to start'}
              </Text>
            </View>

            {/* Transcript */}
            {transcript ? (
              <View style={styles.transcriptBox}>
                <Ionicons name="chatbubble-outline" size={16} color={COLORS.textSecondary} />
                <Text style={styles.transcriptText}>"{transcript}"</Text>
              </View>
            ) : null}

            {/* Last command result */}
            {lastCommand ? (
              <View style={styles.commandResult}>
                <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
                <Text style={styles.commandResultText}>
                  {describeCommand(lastCommand)}
                </Text>
              </View>
            ) : null}

            {/* Error */}
            {error ? (
              <View style={styles.errorBox}>
                <Ionicons name="alert-circle" size={16} color={COLORS.error} />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {/* Command History */}
            {commandHistory.length > 0 && (
              <View style={styles.historySection}>
                <Text style={styles.historyTitle}>Recent Commands</Text>
                {commandHistory.map((item, idx) => (
                  <View key={idx} style={styles.historyItem}>
                    <Ionicons
                      name={item.success ? 'checkmark-circle' : 'close-circle'}
                      size={14}
                      color={item.success ? COLORS.success : COLORS.error}
                    />
                    <Text style={[
                      styles.historyText,
                      !item.success && styles.historyTextError,
                    ]}>{item.text}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Available Factors */}
            <View style={styles.factorList}>
              <Text style={styles.factorListTitle}>Available Factors:</Text>
              <View style={styles.factorChips}>
                {factors.map(f => (
                  <View key={f.id} style={styles.factorChip}>
                    <Text style={styles.factorChipText}>{f.name}</Text>
                  </View>
                ))}
              </View>
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  micButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: 'rgba(142, 36, 170, 0.2)',
  },
  micButtonDisabled: {
    opacity: 0.5,
  },
  micButtonInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  micButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.primary,
  },
  micButtonTextActive: {
    color: '#FFFFFF',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: COLORS.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  closeButton: {
    padding: 4,
  },
  instructions: {
    backgroundColor: COLORS.background,
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
  },
  instructionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 6,
  },
  instructionExample: {
    fontSize: 14,
    color: COLORS.primary,
    fontWeight: '500',
    fontStyle: 'italic',
    marginBottom: 2,
  },
  micArea: {
    alignItems: 'center',
    marginVertical: 20,
  },
  pulseRing: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: COLORS.primary,
  },
  bigMicButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    boxShadow: '0px 4px 8px rgba(124, 58, 237, 0.3)',
  },
  bigMicButtonActive: {
    backgroundColor: COLORS.error,
  },
  micStatus: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 12,
    fontWeight: '500',
  },
  transcriptBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    padding: 12,
    borderRadius: 10,
    gap: 8,
    marginBottom: 8,
  },
  transcriptText: {
    fontSize: 15,
    color: COLORS.textPrimary,
    flex: 1,
    fontStyle: 'italic',
  },
  commandResult: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    padding: 12,
    borderRadius: 10,
    gap: 8,
    marginBottom: 8,
  },
  commandResultText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.success,
    flex: 1,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    padding: 10,
    borderRadius: 8,
    gap: 6,
    marginBottom: 8,
  },
  errorText: {
    fontSize: 13,
    color: COLORS.error,
    flex: 1,
  },
  historySection: {
    marginTop: 8,
    marginBottom: 12,
  },
  historyTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textMuted,
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 4,
  },
  historyText: {
    fontSize: 13,
    color: COLORS.textSecondary,
  },
  historyTextError: {
    color: COLORS.textMuted,
  },
  factorList: {
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  factorListTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textMuted,
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  factorChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  factorChip: {
    backgroundColor: COLORS.background,
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  factorChipText: {
    fontSize: 12,
    color: COLORS.textPrimary,
    fontWeight: '500',
  },
});
