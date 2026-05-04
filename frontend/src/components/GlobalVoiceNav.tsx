/**
 * GlobalVoiceNav.tsx
 *
 * Floating mic bubble for app-wide voice navigation.
 * Post-login only. Visible only on "hub / list" screens where the user
 * picks a module or sub-tool (NOT inside wizard/step screens).
 *
 * Supported languages: en, hi, ta, te, kn, ml
 *
 * Scope: navigation intents only. Step-level voice input continues to be
 * handled by VoiceStepInput (PRR flow) and VoiceAssessmentInput.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Animated,
  Modal, ScrollView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { usePathname, useRouter } from 'expo-router';
import { COLORS } from '../constants/colors';
import { useAuthStore } from '../store/authStore';
import {
  parseRouteCommand, SupportedLanguage, VOICE_NAV_LANGUAGES,
  ROUTE_DICTIONARY,
} from '../utils/routeVoiceParser';

// Conditional import for speech recognition
let ExpoSpeechRecognitionModule: any = null;
let useSpeechRecognitionEvent: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const speechModule = require('expo-speech-recognition');
  ExpoSpeechRecognitionModule = speechModule.ExpoSpeechRecognitionModule;
  useSpeechRecognitionEvent = speechModule.useSpeechRecognitionEvent;
} catch {
  // Module not available (e.g. in web dev). Bubble will render a disabled state.
}

// ----------------------------------------------------------------------
// Visibility rules
// ----------------------------------------------------------------------
// Show on these path prefixes (post-login tool-picker / list screens only).
const SHOW_PREFIXES: string[] = [
  '/(tabs)',
  '/tools/solution-matrix-list',
  '/tools/solution-finder-list',
  '/tools/public-pulse',         // public-pulse hub index
  '/tools/ctt',                  // task-tracker hub
  '/tools/gem',                  // gem hub
  '/tools/lifestyle',            // lifestyle hub
];

// Explicitly hide on these paths even if they match a SHOW_PREFIX.
// Avoid bubble inside wizard / detail screens.
const HIDE_EXACT: string[] = [
  '/(tabs)/profile',            // settings
];
const HIDE_PREFIXES: string[] = [
  '/auth',
  '/prr/',                       // inside PRR wizard
  '/test123/',                   // inside test123 wizard
  '/tools/ctt-task',             // single-task detail
  '/tools/solution-matrix',      // matrix wizard (/tools/solution-matrix without -list)
  '/tools/solution-finder',      // finder wizard (/tools/solution-finder without -list)
  '/tools/gem-goal',
  '/tools/gem-flight',
  '/tools/eg-',                  // emotional-gatekeeper sub-screens
  '/tools/lifestyle-eval',
  '/tools/lifestyle-routine',
  '/tools/tepfi-entry',
  '/tools/aala-entry',
  '/tools/solution-detail',
  '/tools/add-solution',
];

function shouldShowOnPath(pathname: string): boolean {
  if (!pathname) return false;
  if (HIDE_EXACT.some(p => pathname === p || pathname === p.replace('/(tabs)', ''))) return false;
  if (HIDE_PREFIXES.some(p => pathname.startsWith(p))) return false;
  if (SHOW_PREFIXES.some(p => pathname.startsWith(p) || pathname === p.replace('/(tabs)', '') || pathname === '/')) return true;
  // Default: hide elsewhere (conservative)
  return false;
}

// ----------------------------------------------------------------------
// Pulse ring
// ----------------------------------------------------------------------
function PulseRing({ active }: { active: boolean }) {
  const scale = useRef(new Animated.Value(1)).current;
  const opacity = useRef(new Animated.Value(0.6)).current;
  useEffect(() => {
    if (active) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.parallel([
            Animated.timing(scale, { toValue: 1.8, duration: 900, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 0, duration: 900, useNativeDriver: true }),
          ]),
          Animated.parallel([
            Animated.timing(scale, { toValue: 1, duration: 0, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 0.6, duration: 0, useNativeDriver: true }),
          ]),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    }
    scale.setValue(1); opacity.setValue(0.6);
  }, [active, scale, opacity]);
  if (!active) return null;
  return <Animated.View style={[styles.pulseRing, { transform: [{ scale }], opacity }]} />;
}

// ----------------------------------------------------------------------
// GlobalVoiceNav
// ----------------------------------------------------------------------
export default function GlobalVoiceNav() {
  const router = useRouter();
  const pathname = usePathname() || '';
  const { isAuthenticated } = useAuthStore();

  const [open, setOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [language, setLanguage] = useState<SupportedLanguage>('en');
  const [error, setError] = useState('');
  const [available, setAvailable] = useState(false);
  const [lastResult, setLastResult] = useState<string>('');

  const visible = isAuthenticated && shouldShowOnPath(pathname);

  // --- check availability once ---
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        if (!ExpoSpeechRecognitionModule) { setAvailable(false); return; }
        const avail = await ExpoSpeechRecognitionModule.getStateAsync?.().catch(() => null);
        if (!cancel) setAvailable(!!avail);
      } catch { if (!cancel) setAvailable(false); }
    })();
    return () => { cancel = true; };
  }, []);

  // --- speech recognition event hooks (conditional) ---
  if (useSpeechRecognitionEvent) {
    useSpeechRecognitionEvent('start', () => setListening(true));
    useSpeechRecognitionEvent('end', () => setListening(false));
    useSpeechRecognitionEvent('result', (event: any) => {
      try {
        const best = event?.results?.[0]?.transcript || '';
        if (best) {
          setTranscript(best);
          const intent = parseRouteCommand(best, language);
          if (intent) {
            setLastResult(intent.route.label);
            // stop, close and navigate
            try { ExpoSpeechRecognitionModule?.stop?.(); } catch {}
            setTimeout(() => {
              setOpen(false);
              setListening(false);
              router.push(intent.route.path as any);
              setTranscript('');
            }, 160);
          }
        }
      } catch {}
    });
    useSpeechRecognitionEvent('error', (event: any) => {
      const code = event?.error;
      setListening(false);
      if (code && code !== 'no-speech' && code !== 'aborted') setError(String(code));
    });
  }

  const startListening = async () => {
    setError('');
    setTranscript('');
    if (!ExpoSpeechRecognitionModule) {
      setError('Voice not supported on this device.');
      return;
    }
    try {
      const bcp47 = VOICE_NAV_LANGUAGES.find(l => l.code === language)?.bcp47 || 'en-IN';
      const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync?.();
      if (perm && perm.granted === false) {
        setError('Microphone permission denied.');
        return;
      }
      await ExpoSpeechRecognitionModule.start?.({
        lang: bcp47,
        interimResults: true,
        continuous: false,
        maxAlternatives: 1,
        requiresOnDeviceRecognition: false,
      });
      setListening(true);
    } catch (e: any) {
      setError(e?.message || 'Could not start listening');
      setListening(false);
    }
  };

  const stopListening = async () => {
    try { await ExpoSpeechRecognitionModule?.stop?.(); } catch {}
    setListening(false);
  };

  const submitManual = () => {
    const intent = parseRouteCommand(transcript, language);
    if (intent) {
      setOpen(false);
      router.push(intent.route.path as any);
      setTranscript('');
    } else {
      setError('Could not recognise a destination. Try: "open goal setter".');
    }
  };

  const hintLang = language;
  const hintChips = useMemo(() => ROUTE_DICTIONARY.slice(0, 10), []);

  if (!visible) return null;

  return (
    <>
      {/* Floating mic bubble */}
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel="Voice navigation"
        onPress={() => setOpen(true)}
        activeOpacity={0.85}
        style={styles.bubble}
      >
        <PulseRing active={false} />
        <View style={styles.bubbleInner}>
          <Ionicons name="mic" size={22} color="#FFF" />
        </View>
      </TouchableOpacity>

      {/* Panel */}
      <Modal visible={open} animationType="slide" transparent onRequestClose={() => setOpen(false)}>
        <View style={styles.overlay}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.title}>Voice Navigation</Text>
                <Text style={styles.subtitle}>Say a tool name to jump there.</Text>
              </View>
              <TouchableOpacity onPress={() => { stopListening(); setOpen(false); setTranscript(''); }}>
                <Ionicons name="close-circle" size={28} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>

            {/* Language picker */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.langRow}>
              {VOICE_NAV_LANGUAGES.map(l => {
                const sel = l.code === language;
                return (
                  <TouchableOpacity
                    key={l.code}
                    onPress={() => setLanguage(l.code)}
                    style={[styles.langChip, sel && styles.langChipActive]}
                  >
                    <Text style={[styles.langChipText, sel && styles.langChipTextActive]}>
                      {l.nativeLabel}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {/* Mic area */}
            <View style={styles.micArea}>
              <PulseRing active={listening} />
              <TouchableOpacity
                onPress={listening ? stopListening : startListening}
                activeOpacity={0.85}
                style={[styles.bigMic, listening && styles.bigMicActive]}
              >
                <Ionicons name={listening ? 'stop' : 'mic'} size={32} color="#FFF" />
              </TouchableOpacity>
              <Text style={styles.micHint}>
                {listening ? 'Listening... tap to stop' : (available || Platform.OS !== 'web')
                  ? 'Tap the mic, then say the tool name'
                  : 'Voice not available — type instead'}
              </Text>
              {!!transcript && (
                <Text style={styles.transcript}>"{transcript}"</Text>
              )}
              {!!lastResult && !listening && (
                <Text style={styles.lastResult}>Matched: {lastResult}</Text>
              )}
              {!!error && <Text style={styles.errorText}>{error}</Text>}
            </View>

            {/* Manual fallback */}
            {!!transcript && !listening && (
              <TouchableOpacity style={styles.submitBtn} onPress={submitManual}>
                <Ionicons name="send" size={14} color="#FFF" />
                <Text style={styles.submitBtnText}>Try command</Text>
              </TouchableOpacity>
            )}

            {/* Hint chips */}
            <Text style={styles.hintTitle}>Try saying:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hintRow}>
              {hintChips.map(r => {
                const first = (r.keywords[hintLang] || r.keywords.en)[0] || r.label;
                return (
                  <TouchableOpacity
                    key={r.id}
                    style={styles.hintChip}
                    onPress={() => { setOpen(false); router.push(r.path as any); }}
                  >
                    <Ionicons name={r.icon as any} size={12} color={COLORS.primary} />
                    <Text style={styles.hintText}>"{first}"</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  bubble: {
    position: 'absolute',
    right: 16,
    bottom: 90,
    width: 56, height: 56,
    borderRadius: 28,
    backgroundColor: COLORS.primary,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 6,
    alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  bubbleInner: { alignItems: 'center', justifyContent: 'center' },
  pulseRing: {
    position: 'absolute',
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: COLORS.primary + '55',
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 24,
    maxHeight: '78%',
  },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  langRow: { gap: 6, paddingVertical: 8 },
  langChip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: COLORS.white,
    borderWidth: 1, borderColor: COLORS.border,
    marginRight: 6,
  },
  langChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  langChipText: { fontSize: 12, color: COLORS.textPrimary, fontWeight: '600' },
  langChipTextActive: { color: '#FFF' },
  micArea: {
    alignItems: 'center', justifyContent: 'center',
    paddingVertical: 24, position: 'relative',
  },
  bigMic: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: COLORS.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  bigMicActive: { backgroundColor: '#EF4444' },
  micHint: { fontSize: 12, color: COLORS.textMuted, marginTop: 10, textAlign: 'center' },
  transcript: {
    marginTop: 10, fontSize: 14, color: COLORS.textPrimary,
    backgroundColor: COLORS.white,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 12, paddingVertical: 8,
  },
  lastResult: { marginTop: 6, fontSize: 12, fontWeight: '600', color: COLORS.success },
  errorText: { marginTop: 8, fontSize: 12, color: COLORS.error, textAlign: 'center' },
  submitBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'center',
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: COLORS.accent,
    marginBottom: 8,
  },
  submitBtnText: { fontSize: 13, fontWeight: '700', color: '#FFF' },
  hintTitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 10, marginBottom: 6 },
  hintRow: { gap: 6, paddingVertical: 4 },
  hintChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: COLORS.white,
    borderWidth: 1, borderColor: COLORS.border,
    marginRight: 6,
  },
  hintText: { fontSize: 11, color: COLORS.textPrimary, fontWeight: '500' },
});
