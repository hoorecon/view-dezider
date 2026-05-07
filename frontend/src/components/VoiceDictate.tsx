/**
 * <VoiceDictate> — generic voice-to-text mic button.
 *
 * Wraps expo-speech-recognition (native) + Web Speech API (web). Emits each
 * final transcript via `onTranscript` callback. The parent decides what to do
 * with it (append to a TextInput, send to AI classifier, etc.).
 *
 * Usage:
 *   <VoiceDictate onTranscript={(t) => setText(prev => prev + ' ' + t)} />
 *
 * Auto-degrades gracefully:
 *   - Native without expo-speech-recognition → renders nothing (safe no-op)
 *   - Web without Speech API → renders disabled mic with tooltip
 *
 * iOS info.plist + Android permissions are already declared in app.json
 * (added during PRR voice work).
 */
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

let ExpoSpeechRecognitionModule: any = null;
let useSpeechRecognitionEvent: any = null;
try {
  const m = require('expo-speech-recognition');
  ExpoSpeechRecognitionModule = m.ExpoSpeechRecognitionModule;
  useSpeechRecognitionEvent = m.useSpeechRecognitionEvent;
} catch { /* not installed in some envs */ }

interface Props {
  onTranscript: (text: string, isFinal: boolean) => void;
  lang?: string;
  size?: 'sm' | 'md' | 'lg';
  testID?: string;
  /** Stop after each utterance (default true). Set false for continuous dictation. */
  oneShot?: boolean;
}

export function VoiceDictate({ onTranscript, lang = 'en-IN', size = 'md', testID = 'voice-dictate', oneShot = true }: Props) {
  const [available, setAvailable] = useState(true);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interim, setInterim] = useState('');
  const stoppingRef = useRef(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!ExpoSpeechRecognitionModule) {
        // Fall back to Web Speech API on web
        if (Platform.OS === 'web' && typeof window !== 'undefined') {
          // @ts-ignore
          const supported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
          if (alive) setAvailable(supported);
        } else if (alive) {
          setAvailable(false);
        }
      } else if (alive) {
        setAvailable(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Native event hooks (only called if module exists)
  if (useSpeechRecognitionEvent) {
    useSpeechRecognitionEvent('start', () => { setListening(true); setError(null); setInterim(''); });
    useSpeechRecognitionEvent('end', () => { setListening(false); });
    useSpeechRecognitionEvent('result', (event: any) => {
      const r = event.results?.[event.results.length - 1];
      if (r?.transcript) {
        if (r.isFinal) {
          onTranscript(r.transcript, true);
          setInterim('');
          if (oneShot) stop();
        } else {
          setInterim(r.transcript);
          onTranscript(r.transcript, false);
        }
      }
    });
    useSpeechRecognitionEvent('error', (event: any) => {
      setListening(false);
      if (event.error === 'not-allowed') setError('Mic permission denied');
      else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setError(event.message || event.error);
      }
    });
  }

  const start = async () => {
    if (!available) return;
    setError(null);
    stoppingRef.current = false;

    if (ExpoSpeechRecognitionModule) {
      try {
        const { granted } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
        if (!granted) { setError('Mic permission required'); return; }
        await ExpoSpeechRecognitionModule.start({
          lang, interimResults: true, continuous: !oneShot, maxAlternatives: 1, addsPunctuation: true,
        });
      } catch (e: any) {
        if (!e?.message?.includes('already started')) setError(e?.message || 'Mic start failed');
      }
    } else if (Platform.OS === 'web') {
      // Web Speech API fallback
      // @ts-ignore
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { setError('Web Speech API unsupported'); return; }
      const r = new SR();
      r.lang = lang;
      r.interimResults = true;
      r.continuous = !oneShot;
      r.onstart = () => { setListening(true); setInterim(''); };
      r.onend = () => setListening(false);
      r.onerror = (e: any) => { setError(e.error || 'mic error'); setListening(false); };
      r.onresult = (e: any) => {
        const last = e.results[e.results.length - 1];
        const txt = last[0]?.transcript || '';
        if (last.isFinal) {
          onTranscript(txt, true);
          setInterim('');
          if (oneShot) r.stop();
        } else {
          setInterim(txt);
          onTranscript(txt, false);
        }
      };
      try { r.start(); } catch (e: any) { setError(e?.message || 'start failed'); }
    }
  };

  const stop = async () => {
    stoppingRef.current = true;
    if (ExpoSpeechRecognitionModule) {
      try { await ExpoSpeechRecognitionModule.stop(); } catch { /* ignore */ }
    }
    setListening(false);
  };

  const toggle = () => listening ? stop() : start();

  if (!available) {
    return (
      <View style={[s.btn, s.disabled, sizeStyle(size)]}>
        <Ionicons name="mic-off" size={iconSize(size)} color={COLORS.textMuted} />
      </View>
    );
  }

  return (
    <View>
      <TouchableOpacity testID={testID} onPress={toggle} style={[s.btn, listening ? s.listening : s.idle, sizeStyle(size)]}>
        {listening ? (
          <ActivityIndicator color="#FFF" size="small" />
        ) : (
          <Ionicons name="mic" size={iconSize(size)} color={listening ? '#FFF' : COLORS.primary} />
        )}
      </TouchableOpacity>
      {!!interim && (
        <Text style={s.interim} numberOfLines={2}>"{interim}"</Text>
      )}
      {!!error && <Text style={s.error}>{error}</Text>}
    </View>
  );
}

function sizeStyle(z: 'sm' | 'md' | 'lg') {
  const d = z === 'sm' ? 32 : z === 'lg' ? 56 : 44;
  return { width: d, height: d, borderRadius: d / 2 };
}
function iconSize(z: 'sm' | 'md' | 'lg') {
  return z === 'sm' ? 14 : z === 'lg' ? 24 : 18;
}

const s = StyleSheet.create({
  btn: { alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  idle: { backgroundColor: COLORS.white, borderColor: COLORS.primary },
  listening: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  disabled: { backgroundColor: '#F3F4F6', borderColor: COLORS.divider },
  interim: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, fontStyle: 'italic', maxWidth: 200 },
  error: { fontSize: 10, color: '#DC2626', marginTop: 4, maxWidth: 200 },
});
