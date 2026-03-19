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
import {
  parseStepVoiceCommand,
  getStepVoiceHints,
  describeStepCommand,
  StepVoiceCommand,
} from '../utils/stepVoiceParser';

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

interface Option {
  id: string;
  name: string;
}

interface VoiceStepInputProps {
  step: number;
  factors: Factor[];
  options: Option[];
  onCommand: (command: StepVoiceCommand) => void;
  disabled?: boolean;
}

// Animated pulse ring
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
      style={[styles.pulseRing, { transform: [{ scale }], opacity }]}
    />
  );
}

export default function VoiceStepInput({ step, factors, options, onCommand, disabled }: VoiceStepInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [panelVisible, setPanelVisible] = useState(false);
  const [error, setError] = useState('');
  const [isAvailable, setIsAvailable] = useState(false);
  const [commandHistory, setCommandHistory] = useState<Array<{ text: string; success: boolean }>>([]);
  const [commandCount, setCommandCount] = useState(0);
  const [lastApplied, setLastApplied] = useState('');

  const panelAnim = useRef(new Animated.Value(0)).current;
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isStoppingRef = useRef(false);

  const hints = getStepVoiceHints(step);

  useEffect(() => {
    checkAvailability();
  }, []);

  useEffect(() => {
    Animated.spring(panelAnim, {
      toValue: panelVisible ? 1 : 0,
      useNativeDriver: true,
      friction: 8,
    }).start();
  }, [panelVisible]);

  // Close panel when step changes
  useEffect(() => {
    if (panelVisible) {
      closePanel();
    }
  }, [step]);

  const checkAvailability = async () => {
    if (!ExpoSpeechRecognitionModule) { setIsAvailable(false); return; }
    try {
      if (Platform.OS === 'web') {
        const supported = typeof window !== 'undefined' &&
          ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
        setIsAvailable(supported);
      } else {
        setIsAvailable(true);
      }
    } catch { setIsAvailable(false); }
  };

  if (useSpeechRecognitionEvent) {
    useSpeechRecognitionEvent('start', () => {
      setIsListening(true);
      setTranscript('');
      setError('');
    });

    useSpeechRecognitionEvent('end', () => {
      setIsListening(false);
      if (panelVisible && !isStoppingRef.current) {
        restartTimerRef.current = setTimeout(() => {
          if (panelVisible && !isStoppingRef.current) startRecognition();
        }, 600);
      }
    });

    useSpeechRecognitionEvent('result', (event: any) => {
      const result = event.results?.[event.results.length - 1];
      if (result?.transcript) {
        setTranscript(result.transcript);
        if (result.isFinal || !event.results?.some?.((r: any) => !r.isFinal)) {
          processTranscript(result.transcript);
        }
      }
    });

    useSpeechRecognitionEvent('error', (event: any) => {
      setIsListening(false);
      if (event.error === 'no-speech') {
        if (panelVisible && !isStoppingRef.current) {
          restartTimerRef.current = setTimeout(() => {
            if (panelVisible && !isStoppingRef.current) startRecognition();
          }, 300);
        }
      } else if (event.error === 'not-allowed') {
        setError('Microphone permission denied.');
      } else if (event.error !== 'aborted') {
        setError(`Error: ${event.message || event.error}`);
      }
    });
  }

  const processTranscript = useCallback((text: string) => {
    const command = parseStepVoiceCommand(step, text, factors, options);

    if (command && command.confidence >= 0.4) {
      onCommand(command);
      setCommandCount(prev => prev + 1);
      const desc = describeStepCommand(command);
      setLastApplied(desc);
      setCommandHistory(prev => [
        { text: desc, success: true },
        ...prev.slice(0, 9),
      ]);
    } else {
      setCommandHistory(prev => [
        { text: `"${text}" — not recognized`, success: false },
        ...prev.slice(0, 9),
      ]);
    }
  }, [step, factors, options, onCommand]);

  const startRecognition = async () => {
    if (!ExpoSpeechRecognitionModule || !isAvailable) return;
    try {
      const { granted } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!granted) { setError('Microphone permission required'); return; }

      const contextStrings = [
        ...factors.map(f => f.name),
        ...options.map(o => o.name),
        'high', 'medium', 'low', 'percent', 'add', 'remove', 'primary', 'secondary',
        'move', 'up', 'down', 'first', 'choose', 'select', 'all', 'title', 'context',
      ];

      await ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        continuous: true,
        maxAlternatives: 1,
        addsPunctuation: false,
        contextualStrings: contextStrings,
      });
    } catch (err: any) {
      if (err.message?.includes('already started')) return;
      setError(err.message || 'Failed to start');
    }
  };

  const openPanel = async () => {
    if (!isAvailable) { setError('Voice not available'); return; }
    setError('');
    setTranscript('');
    isStoppingRef.current = false;
    setPanelVisible(true);
    setTimeout(() => startRecognition(), 300);
  };

  const stopListening = async () => {
    isStoppingRef.current = true;
    if (restartTimerRef.current) { clearTimeout(restartTimerRef.current); restartTimerRef.current = null; }
    if (ExpoSpeechRecognitionModule) {
      try { await ExpoSpeechRecognitionModule.stop(); } catch {}
    }
    setIsListening(false);
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

  // Skip steps that don't support voice (Step 5)
  if (step === 5) return null;
  if (!isAvailable && !ExpoSpeechRecognitionModule) return null;

  return (
    <>
      {/* Mic Trigger Button */}
      <TouchableOpacity
        style={[styles.micButton, disabled && styles.micButtonDisabled, panelVisible && styles.micButtonActive]}
        onPress={() => panelVisible ? closePanel() : openPanel()}
        disabled={disabled}
        activeOpacity={0.7}
      >
        <Ionicons
          name={panelVisible ? 'mic' : 'mic-outline'}
          size={18}
          color={panelVisible ? '#FFF' : COLORS.primary}
        />
        <Text style={[styles.micButtonText, panelVisible && styles.micButtonTextActive]}>
          {panelVisible ? 'Listening...' : 'Voice'}
        </Text>
        {commandCount > 0 && !panelVisible && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{commandCount}</Text>
          </View>
        )}
      </TouchableOpacity>

      {/* Floating Panel */}
      {panelVisible && (
        <Animated.View
          style={[
            styles.panel,
            {
              transform: [{ translateY: panelAnim.interpolate({ inputRange: [0, 1], outputRange: [200, 0] }) }],
              opacity: panelAnim,
            },
          ]}
        >
          <View style={styles.panelDragRow}><View style={styles.dragHandle} /></View>

          <View style={styles.panelRow}>
            {/* Mic */}
            <View style={styles.micCol}>
              <View style={styles.micWrap}>
                <PulseRing isActive={isListening} />
                <TouchableOpacity
                  style={[styles.bigMic, isListening && styles.bigMicActive]}
                  onPress={toggleMic}
                >
                  <Ionicons name={isListening ? 'mic' : 'mic-off-outline'} size={22} color="#FFF" />
                </TouchableOpacity>
              </View>
              <Text style={styles.micLabel}>{isListening ? 'Listening' : 'Paused'}</Text>
            </View>

            {/* Info */}
            <View style={styles.infoCol}>
              {transcript ? (
                <View style={styles.transcriptRow}>
                  <Ionicons name="chatbubble-ellipses-outline" size={13} color={COLORS.primary} />
                  <Text style={styles.transcriptText} numberOfLines={2}>"{transcript}"</Text>
                </View>
              ) : isListening ? (
                <View style={styles.transcriptRow}>
                  <Text style={styles.hintText} numberOfLines={2}>{hints.examples[0] || hints.description}</Text>
                </View>
              ) : null}

              {lastApplied ? (
                <View style={styles.appliedRow}>
                  <Ionicons name="checkmark-circle" size={13} color={COLORS.success} />
                  <Text style={styles.appliedText} numberOfLines={1}>{lastApplied}</Text>
                </View>
              ) : null}

              {error ? (
                <View style={styles.errorRow}>
                  <Ionicons name="alert-circle" size={13} color={COLORS.error} />
                  <Text style={styles.errorText} numberOfLines={1}>{error}</Text>
                </View>
              ) : null}

              {commandHistory.length > 0 && (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.historyScroll}>
                  {commandHistory.slice(0, 5).map((item, idx) => (
                    <View key={idx} style={[styles.chip, item.success ? styles.chipOk : styles.chipFail]}>
                      <Ionicons name={item.success ? 'checkmark' : 'close'} size={10} color={item.success ? COLORS.success : COLORS.error} />
                      <Text style={styles.chipText} numberOfLines={1}>{item.text}</Text>
                    </View>
                  ))}
                </ScrollView>
              )}
            </View>

            <TouchableOpacity onPress={closePanel} style={styles.closeBtn}>
              <Ionicons name="close" size={18} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {/* Context chips */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsScroll} contentContainerStyle={styles.chipsContent}>
            {(step <= 4 || step === 7 ? factors : options).map(item => (
              <View key={item.id} style={styles.ctxChip}>
                <Text style={styles.ctxChipText} numberOfLines={1}>{item.name}</Text>
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
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(142,36,170,0.08)', borderRadius: 18,
    paddingHorizontal: 12, paddingVertical: 7,
    borderWidth: 1, borderColor: 'rgba(142,36,170,0.2)',
  },
  micButtonDisabled: { opacity: 0.5 },
  micButtonActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  micButtonText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },
  micButtonTextActive: { color: '#FFF' },
  badge: {
    backgroundColor: COLORS.success, borderRadius: 9, width: 18, height: 18,
    justifyContent: 'center', alignItems: 'center', marginLeft: 2,
  },
  badgeText: { fontSize: 9, fontWeight: '700', color: '#FFF' },

  panel: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: 'rgba(255,255,255,0.97)',
    borderTopLeftRadius: 18, borderTopRightRadius: 18,
    boxShadow: '0px -3px 16px rgba(0,0,0,0.12)',
    elevation: 10, zIndex: 100,
    paddingBottom: Platform.OS === 'ios' ? 34 : 12,
  },
  panelDragRow: { alignItems: 'center', paddingTop: 6, paddingBottom: 2 },
  dragHandle: { width: 32, height: 4, borderRadius: 2, backgroundColor: COLORS.border },

  panelRow: { flexDirection: 'row', alignItems: 'flex-start', paddingHorizontal: 14, paddingVertical: 6, gap: 10 },

  micCol: { alignItems: 'center', gap: 3 },
  micWrap: { width: 44, height: 44, justifyContent: 'center', alignItems: 'center' },
  pulseRing: { position: 'absolute', width: 44, height: 44, borderRadius: 22, backgroundColor: COLORS.primary },
  bigMic: {
    width: 42, height: 42, borderRadius: 21,
    backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center',
    elevation: 3, boxShadow: '0px 2px 6px rgba(124,58,237,0.3)',
  },
  bigMicActive: { backgroundColor: '#E53E3E' },
  micLabel: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase' },

  infoCol: { flex: 1, gap: 3 },
  transcriptRow: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(142,36,170,0.06)', paddingHorizontal: 8, paddingVertical: 5, borderRadius: 7,
  },
  transcriptText: { fontSize: 12, color: COLORS.primary, fontWeight: '500', flex: 1, fontStyle: 'italic' },
  hintText: { fontSize: 11, color: COLORS.textMuted, flex: 1, fontStyle: 'italic' },
  appliedRow: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(16,185,129,0.08)', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 7,
  },
  appliedText: { fontSize: 11, fontWeight: '600', color: COLORS.success, flex: 1 },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 8, paddingVertical: 3 },
  errorText: { fontSize: 10, color: COLORS.error, flex: 1 },

  historyScroll: { flexGrow: 0, marginTop: 1 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 10, marginRight: 5 },
  chipOk: { backgroundColor: 'rgba(16,185,129,0.1)' },
  chipFail: { backgroundColor: 'rgba(239,68,68,0.08)' },
  chipText: { fontSize: 9, color: COLORS.textSecondary, maxWidth: 110 },

  closeBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center' },

  chipsScroll: { flexGrow: 0, paddingHorizontal: 14, paddingBottom: 6 },
  chipsContent: { gap: 5 },
  ctxChip: {
    backgroundColor: COLORS.background, borderRadius: 12,
    paddingHorizontal: 9, paddingVertical: 3,
    borderWidth: 1, borderColor: COLORS.border,
  },
  ctxChipText: { fontSize: 10, color: COLORS.textSecondary, fontWeight: '500' },
});
