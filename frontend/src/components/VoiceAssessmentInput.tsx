import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Platform,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { parseVoiceCommand, describeCommand, ParsedVoiceCommand } from '../utils/voiceCommandParser';

// Conditional import for speech recognition
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
            Animated.timing(scale, { toValue: 1.6, duration: 800, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 0, duration: 800, useNativeDriver: true }),
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

// Small flash animation for applied commands
function FlashBadge({ children, flash }: { children: React.ReactNode; flash: boolean }) {
  const bgOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (flash) {
      Animated.sequence([
        Animated.timing(bgOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.timing(bgOpacity, { toValue: 0, duration: 800, useNativeDriver: true }),
      ]).start();
    }
  }, [flash]);

  return (
    <View>
      <Animated.View style={[styles.flashOverlay, { opacity: bgOpacity }]} />
      {children}
    </View>
  );
}

export default function VoiceAssessmentInput({ factors, onCommand, disabled }: VoiceAssessmentInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [lastCommand, setLastCommand] = useState<ParsedVoiceCommand | null>(null);
  const [panelVisible, setPanelVisible] = useState(false);
  const [error, setError] = useState('');
  const [isAvailable, setIsAvailable] = useState(false);
  const [commandHistory, setCommandHistory] = useState<Array<{ text: string; success: boolean; timestamp: number }>>([]);
  const [continuousMode, setContinuousMode] = useState(true);
  const [commandCount, setCommandCount] = useState(0);
  const [lastFlashedFactor, setLastFlashedFactor] = useState<string | null>(null);

  const micScale = useRef(new Animated.Value(1)).current;
  const panelAnim = useRef(new Animated.Value(0)).current;
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isStoppingRef = useRef(false);

  // Check availability on mount
  useEffect(() => {
    checkAvailability();
  }, []);

  // Animate panel in/out
  useEffect(() => {
    Animated.spring(panelAnim, {
      toValue: panelVisible ? 1 : 0,
      useNativeDriver: true,
      friction: 8,
    }).start();
  }, [panelVisible]);

  const checkAvailability = async () => {
    if (!ExpoSpeechRecognitionModule) {
      setIsAvailable(false);
      return;
    }
    try {
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
      // Auto-restart in continuous mode
      if (continuousMode && panelVisible && !isStoppingRef.current) {
        restartTimerRef.current = setTimeout(() => {
          if (panelVisible && !isStoppingRef.current) {
            startRecognition();
          }
        }, 600);
      }
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
        // In continuous mode, just restart silently
        if (continuousMode && panelVisible && !isStoppingRef.current) {
          restartTimerRef.current = setTimeout(() => {
            if (panelVisible && !isStoppingRef.current) {
              startRecognition();
            }
          }, 300);
        } else {
          setError('No speech detected. Tap mic to try again.');
        }
      } else if (event.error === 'not-allowed') {
        setError('Microphone permission denied.');
      } else if (event.error === 'aborted') {
        // Silently handle abort (happens during restart)
      } else {
        setError(`Error: ${event.message || event.error}`);
      }
    });
  }

  const processTranscript = useCallback((text: string) => {
    const command = parseVoiceCommand(text, factors);

    if (command && command.confidence >= 0.4 && (command.factorId || command.allFactors)) {
      setLastCommand(command);
      onCommand(command);
      setCommandCount(prev => prev + 1);

      // Flash the factor that was updated
      if (command.factorId) {
        setLastFlashedFactor(command.factorId);
        setTimeout(() => setLastFlashedFactor(null), 1500);
      } else if (command.allFactors) {
        setLastFlashedFactor('all');
        setTimeout(() => setLastFlashedFactor(null), 1500);
      }

      setCommandHistory(prev => [
        { text: describeCommand(command), success: true, timestamp: Date.now() },
        ...prev.slice(0, 9),
      ]);
    } else {
      setCommandHistory(prev => [
        { text: `"${text}" — not recognized`, success: false, timestamp: Date.now() },
        ...prev.slice(0, 9),
      ]);
    }
  }, [factors, onCommand]);

  const startRecognition = async () => {
    if (!ExpoSpeechRecognitionModule || !isAvailable) return;

    try {
      const { granted } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!granted) {
        setError('Microphone permission required');
        return;
      }

      await ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        continuous: true,
        maxAlternatives: 1,
        addsPunctuation: false,
        contextualStrings: [
          ...factors.map(f => f.name),
          'high', 'medium', 'low', 'percent',
          'all', 'every', 'next',
        ],
      });
    } catch (err: any) {
      // If already started, ignore
      if (err.message?.includes('already started')) return;
      console.error('Start error:', err);
      setError(err.message || 'Failed to start voice input');
    }
  };

  const openPanel = async () => {
    if (!ExpoSpeechRecognitionModule || !isAvailable) {
      setError('Voice input not available on this device/browser');
      return;
    }

    setError('');
    setTranscript('');
    setLastCommand(null);
    isStoppingRef.current = false;
    setPanelVisible(true);

    // Small delay before starting recognition
    setTimeout(() => {
      startRecognition();
    }, 300);

    Animated.spring(micScale, {
      toValue: 0.9,
      useNativeDriver: true,
    }).start();
  };

  const stopListening = async () => {
    isStoppingRef.current = true;
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
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

  const closePanel = () => {
    stopListening();
    setPanelVisible(false);
    setTranscript('');
    setError('');
  };

  const toggleMic = () => {
    if (isListening) {
      stopListening();
    } else {
      isStoppingRef.current = false;
      startRecognition();
    }
  };

  if (!isAvailable && !ExpoSpeechRecognitionModule) {
    return null;
  }

  return (
    <>
      {/* Compact Mic Trigger Button */}
      <TouchableOpacity
        style={[styles.micButton, disabled && styles.micButtonDisabled, panelVisible && styles.micButtonActive]}
        onPress={() => {
          if (panelVisible) {
            closePanel();
          } else {
            openPanel();
          }
        }}
        disabled={disabled}
        activeOpacity={0.7}
      >
        <View style={styles.micButtonInner}>
          <Ionicons
            name={panelVisible ? 'mic' : 'mic-outline'}
            size={20}
            color={panelVisible ? '#FFFFFF' : COLORS.primary}
          />
          <Text style={[styles.micButtonText, panelVisible && styles.micButtonTextActive]}>
            {panelVisible ? 'Listening...' : 'Voice Input'}
          </Text>
          {commandCount > 0 && !panelVisible && (
            <View style={styles.commandCountBadge}>
              <Text style={styles.commandCountText}>{commandCount}</Text>
            </View>
          )}
        </View>
      </TouchableOpacity>

      {/* Floating Compact Panel - NOT a modal, so matrix stays visible */}
      {panelVisible && (
        <Animated.View
          style={[
            styles.floatingPanel,
            {
              transform: [{
                translateY: panelAnim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [200, 0],
                })
              }],
              opacity: panelAnim,
            },
          ]}
        >
          {/* Panel Header */}
          <View style={styles.panelHeader}>
            <View style={styles.panelDragHandle} />
          </View>

          <View style={styles.panelBody}>
            {/* Left: Mic button + status */}
            <View style={styles.panelMicSection}>
              <View style={styles.micContainer}>
                <PulseRing isActive={isListening} />
                <TouchableOpacity
                  style={[styles.panelMicBtn, isListening && styles.panelMicBtnActive]}
                  onPress={toggleMic}
                  activeOpacity={0.8}
                >
                  <Ionicons
                    name={isListening ? 'mic' : 'mic-off-outline'}
                    size={24}
                    color="#FFFFFF"
                  />
                </TouchableOpacity>
              </View>
              <Text style={styles.micLabel}>
                {isListening ? 'Listening...' : 'Paused'}
              </Text>
            </View>

            {/* Right: Transcript + Commands */}
            <View style={styles.panelInfoSection}>
              {/* Current transcript */}
              {transcript ? (
                <View style={styles.liveTranscript}>
                  <Ionicons name="chatbubble-ellipses-outline" size={14} color={COLORS.primary} />
                  <Text style={styles.liveTranscriptText} numberOfLines={2}>"{transcript}"</Text>
                </View>
              ) : isListening ? (
                <View style={styles.liveTranscript}>
                  <Ionicons name="chatbubble-ellipses-outline" size={14} color={COLORS.textMuted} />
                  <Text style={styles.liveTranscriptHint}>Say: "Salary High" or "All Medium"</Text>
                </View>
              ) : null}

              {/* Last applied command */}
              {lastCommand && (
                <View style={styles.appliedCommand}>
                  <Ionicons name="checkmark-circle" size={14} color={COLORS.success} />
                  <Text style={styles.appliedCommandText} numberOfLines={1}>
                    Applied: {describeCommand(lastCommand)}
                  </Text>
                </View>
              )}

              {/* Error */}
              {error ? (
                <View style={styles.panelError}>
                  <Ionicons name="alert-circle" size={14} color={COLORS.error} />
                  <Text style={styles.panelErrorText} numberOfLines={1}>{error}</Text>
                </View>
              ) : null}

              {/* Command History (scrollable, compact) */}
              {commandHistory.length > 0 && (
                <ScrollView
                  style={styles.historyScroll}
                  horizontal
                  showsHorizontalScrollIndicator={false}
                >
                  {commandHistory.slice(0, 5).map((item, idx) => (
                    <View
                      key={idx}
                      style={[
                        styles.historyChip,
                        item.success ? styles.historyChipSuccess : styles.historyChipFail,
                      ]}
                    >
                      <Ionicons
                        name={item.success ? 'checkmark' : 'close'}
                        size={10}
                        color={item.success ? COLORS.success : COLORS.error}
                      />
                      <Text style={styles.historyChipText} numberOfLines={1}>
                        {item.text}
                      </Text>
                    </View>
                  ))}
                </ScrollView>
              )}
            </View>

            {/* Close button */}
            <TouchableOpacity onPress={closePanel} style={styles.panelCloseBtn}>
              <Ionicons name="close" size={20} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {/* Factor chips - compact row showing which factors are available */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.factorChipsScroll}
            contentContainerStyle={styles.factorChipsContent}
          >
            {factors.map(f => (
              <View
                key={f.id}
                style={[
                  styles.factorChip,
                  lastFlashedFactor === f.id && styles.factorChipActive,
                  lastFlashedFactor === 'all' && styles.factorChipActive,
                ]}
              >
                <Text
                  style={[
                    styles.factorChipText,
                    (lastFlashedFactor === f.id || lastFlashedFactor === 'all') && styles.factorChipTextActive,
                  ]}
                  numberOfLines={1}
                >
                  {f.name}
                </Text>
              </View>
            ))}
          </ScrollView>
        </Animated.View>
      )}
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
  micButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
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
  commandCountBadge: {
    backgroundColor: COLORS.success,
    borderRadius: 10,
    width: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 2,
  },
  commandCountText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFFFFF',
  },

  // Floating panel styles - positioned at bottom, compact, semi-transparent
  floatingPanel: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(255, 255, 255, 0.97)',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    boxShadow: '0px -4px 20px rgba(0, 0, 0, 0.15)',
    elevation: 10,
    zIndex: 100,
    paddingBottom: Platform.OS === 'ios' ? 34 : 16,
  },
  panelHeader: {
    alignItems: 'center',
    paddingTop: 8,
    paddingBottom: 4,
  },
  panelDragHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: COLORS.border,
  },

  panelBody: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
  },

  // Mic section
  panelMicSection: {
    alignItems: 'center',
    gap: 4,
  },
  micContainer: {
    width: 52,
    height: 52,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pulseRing: {
    position: 'absolute',
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: COLORS.primary,
  },
  panelMicBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    boxShadow: '0px 2px 8px rgba(124, 58, 237, 0.3)',
  },
  panelMicBtnActive: {
    backgroundColor: '#E53E3E',
  },
  micLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Info section
  panelInfoSection: {
    flex: 1,
    gap: 4,
  },
  liveTranscript: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(142, 36, 170, 0.06)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  liveTranscriptText: {
    fontSize: 13,
    color: COLORS.primary,
    fontWeight: '500',
    flex: 1,
    fontStyle: 'italic',
  },
  liveTranscriptHint: {
    fontSize: 12,
    color: COLORS.textMuted,
    flex: 1,
    fontStyle: 'italic',
  },
  appliedCommand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  appliedCommandText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.success,
    flex: 1,
  },
  panelError: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  panelErrorText: {
    fontSize: 11,
    color: COLORS.error,
    flex: 1,
  },

  // History chips (horizontal scroll)
  historyScroll: {
    flexGrow: 0,
    marginTop: 2,
  },
  historyChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginRight: 6,
  },
  historyChipSuccess: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
  },
  historyChipFail: {
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
  },
  historyChipText: {
    fontSize: 10,
    color: COLORS.textSecondary,
    maxWidth: 120,
  },

  // Close button
  panelCloseBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Factor chips at bottom of panel
  factorChipsScroll: {
    flexGrow: 0,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  factorChipsContent: {
    gap: 6,
    paddingRight: 16,
  },
  factorChip: {
    backgroundColor: COLORS.background,
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  factorChipActive: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: COLORS.success,
  },
  factorChipText: {
    fontSize: 11,
    color: COLORS.textSecondary,
    fontWeight: '500',
  },
  factorChipTextActive: {
    color: COLORS.success,
    fontWeight: '700',
  },

  // Flash overlay
  flashOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    borderRadius: 8,
  },
});
