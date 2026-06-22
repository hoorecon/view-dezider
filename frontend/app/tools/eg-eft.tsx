import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Image, Platform, KeyboardAvoidingView,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { WebView } from 'react-native-webview';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { Alert } from '../../src/utils/crossAlert';
const showAlert = (title: string, message?: string) => Alert.alert(title, message);

const EFT = {
  teal: '#14B8A6',
  tealDark: '#0D9488',
  tealLight: '#F0FDFA',
  green: '#10B981',
  amber: '#F59E0B',
  red: '#EF4444',
};

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Step = 'type' | 'subject' | 'intensity_before' | 'affirmation' | 'tapping' | 'intensity_after' | 'result';
const MAIN_STEPS: Step[] = ['type', 'subject', 'intensity_before', 'affirmation', 'tapping', 'intensity_after'];

interface TapPoint { id: string; name: string; instruction: string; is_setup?: boolean; image_url?: string; }

interface EftConfig {
  enabled: boolean;
  title: string;
  description: string;
  affirmation_template_emotion: string;
  affirmation_template_problem: string;
  alt_affirmation_template_emotion: string;
  alt_affirmation_template_problem: string;
  tapping_instructions: string;
  tapping_points: TapPoint[];
  diagram_image_url: string;
  video_url: string;
  disclaimer: string;
  safety_keywords: string[];
  safety_message: string;
}

// Convert a share URL into an embeddable HTML doc for the WebView.
function buildMediaHtml(rawUrl: string): string {
  let url = (rawUrl || '').trim();
  if (url.startsWith('/')) url = `${BACKEND}${url}`;
  const lower = url.toLowerCase();
  let inner = '';
  if (/\.(mp4|webm|ogg|mov)(\?|$)/.test(lower) || lower.includes('/api/static/eft/')) {
    inner = `<video controls playsinline style="width:100%;height:100%;background:#000" src="${url}"></video>`;
  } else if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
    let id = '';
    const m1 = url.match(/[?&]v=([^&]+)/);
    const m2 = url.match(/youtu\.be\/([^?&]+)/);
    const m3 = url.match(/embed\/([^?&]+)/);
    id = (m1 && m1[1]) || (m2 && m2[1]) || (m3 && m3[1]) || '';
    inner = `<iframe src="https://www.youtube.com/embed/${id}" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="width:100%;height:100%"></iframe>`;
  } else if (lower.includes('vimeo.com')) {
    // Handle https://vimeo.com/<id>/<hash> and player.vimeo links.
    const m = url.match(/vimeo\.com\/(?:video\/)?(\d+)(?:\/([0-9a-zA-Z]+))?/);
    const id = m ? m[1] : '';
    const hash = m && m[2] ? `?h=${m[2]}` : '';
    inner = `<iframe src="https://player.vimeo.com/video/${id}${hash}" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen style="width:100%;height:100%"></iframe>`;
  } else {
    inner = `<iframe src="${url}" frameborder="0" allowfullscreen style="width:100%;height:100%"></iframe>`;
  }
  return `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>*{margin:0;padding:0;box-sizing:border-box}html,body{height:100%;background:#000;overflow:hidden}</style></head><body>${inner}</body></html>`;
}

// Resolve a share URL into an embeddable src + kind (web path).
function resolveMediaSrc(rawUrl: string): { kind: 'video' | 'iframe'; src: string } {
  let url = (rawUrl || '').trim();
  if (url.startsWith('/')) url = `${BACKEND}${url}`;
  const lower = url.toLowerCase();
  if (/\.(mp4|webm|ogg|mov)(\?|$)/.test(lower) || lower.includes('/api/static/eft/')) {
    return { kind: 'video', src: url };
  }
  if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
    const m1 = url.match(/[?&]v=([^&]+)/);
    const m2 = url.match(/youtu\.be\/([^?&]+)/);
    const m3 = url.match(/embed\/([^?&]+)/);
    const id = (m1 && m1[1]) || (m2 && m2[1]) || (m3 && m3[1]) || '';
    return { kind: 'iframe', src: `https://www.youtube.com/embed/${id}` };
  }
  if (lower.includes('vimeo.com')) {
    const m = url.match(/vimeo\.com\/(?:video\/)?(\d+)(?:\/([0-9a-zA-Z]+))?/);
    const id = m ? m[1] : '';
    const hash = m && m[2] ? `?h=${m[2]}` : '';
    return { kind: 'iframe', src: `https://player.vimeo.com/video/${id}${hash}` };
  }
  return { kind: 'iframe', src: url };
}

// Cross-platform media embed. react-native-webview is NOT supported on web
// (react-native-web), so on web we render a real DOM <iframe>/<video>; on
// native we fall back to the WebView with an HTML document.
function MediaEmbed({ url, onError }: { url: string; onError?: () => void }) {
  if (Platform.OS === 'web') {
    const { kind, src } = resolveMediaSrc(url);
    const style: any = { width: '100%', height: '100%', border: '0', backgroundColor: '#000' };
    if (kind === 'video') {
      return React.createElement('video', { src, controls: true, playsInline: true, style, onError });
    }
    return React.createElement('iframe', {
      src, style, allowFullScreen: true,
      allow: 'autoplay; fullscreen; picture-in-picture; encrypted-media',
    });
  }
  return (
    <WebView
      testID="eft-video"
      source={{ html: buildMediaHtml(url) }}
      style={{ flex: 1, backgroundColor: '#000' }}
      originWhitelist={['*']}
      javaScriptEnabled
      allowsFullscreenVideo
      onError={onError}
      onHttpError={onError}
    />
  );
}

export default function EftTappingScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const [sessionId, setSessionId] = useState<string | null>((params.sessionId as string) || null);

  const [config, setConfig] = useState<EftConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState<Step>('type');
  const [pointIdx, setPointIdx] = useState(0);

  const [selectedType, setSelectedType] = useState<'emotion' | 'problem' | null>(null);
  const [subjectText, setSubjectText] = useState('');
  const [initialIntensity, setInitialIntensity] = useState<number | null>(null);
  const [finalIntensity, setFinalIntensity] = useState<number | null>(null);
  const [rounds, setRounds] = useState(1);
  const [reflection, setReflection] = useState('');
  const [safetyFlagged, setSafetyFlagged] = useState(false);
  const [showSafety, setShowSafety] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load config and, when resuming, restore previously entered data.
  // NOTE: we do NOT eagerly create a session here — that produced empty
  // "draft" rows. The session is created lazily on the first save.
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/emotional-gatekeeper/eft/config');
        setConfig(res.data);
      } catch {
        showAlert('Error', 'Could not load EFT content. Please try again.');
        setLoading(false);
        return;
      }
      if (sessionId) {
        try {
          const s = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
          const r = s.data?.eft_reflection;
          if (r) {
            if (r.selected_type) setSelectedType(r.selected_type);
            if (r.subject_text) setSubjectText(r.subject_text);
            if (typeof r.initial_intensity_score === 'number') setInitialIntensity(r.initial_intensity_score);
            if (typeof r.final_intensity_score === 'number') setFinalIntensity(r.final_intensity_score);
            if (r.rounds_completed) setRounds(r.rounds_completed);
            if (r.user_reflection) setReflection(r.user_reflection);
            if (r.safety_flagged) setSafetyFlagged(true);
            // Jump to the furthest step the saved data supports.
            if (typeof r.final_intensity_score === 'number') setStep('result');
            else if (typeof r.initial_intensity_score === 'number') setStep('affirmation');
            else if (r.subject_text) setStep('intensity_before');
            else if (r.selected_type) setStep('subject');
          }
        } catch { /* ignore — start fresh */ }
      }
      setLoading(false);
    })();
  }, []);

  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionId) return sessionId;
    try {
      const s = await api.post('/emotional-gatekeeper/sessions', { session_type: 'eft' });
      setSessionId(s.data.id);
      return s.data.id;
    } catch { return null; }
  }, [sessionId]);

  const affirmation = useMemo(() => {
    if (!config || !selectedType) return '';
    const tpl = selectedType === 'emotion'
      ? config.affirmation_template_emotion
      : config.affirmation_template_problem;
    return tpl.replace('{input}', subjectText.trim());
  }, [config, selectedType, subjectText]);

  const reminderPhrase = useMemo(() => {
    if (!subjectText.trim()) return selectedType === 'emotion' ? 'This feeling.' : 'This problem.';
    if (selectedType === 'emotion') return `This ${subjectText.trim().toLowerCase()}.`;
    const kw = subjectText.trim().split(/\s+/).slice(0, 6).join(' ');
    return `This worry about ${kw.toLowerCase()}.`;
  }, [subjectText, selectedType]);

  const points = config?.tapping_points || [];

  // ---------- Hands-free voice control (web Speech API only) ----------
  const voiceSupported = Platform.OS === 'web' && typeof window !== 'undefined'
    && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const [voiceOn, setVoiceOn] = useState(false);
  const [listening, setListening] = useState(false);
  const recogRef = useRef<any>(null);
  const advanceRef = useRef<() => void>(() => {});
  const backRef = useRef<() => void>(() => {});
  const voiceOnRef = useRef(false);
  const stepRef = useRef<Step>(step);
  voiceOnRef.current = voiceOn;
  stepRef.current = step;

  // Keep the navigation actions fresh for both buttons and voice.
  useEffect(() => {
    advanceRef.current = () => {
      if (pointIdx < points.length - 1) setPointIdx((i) => i + 1);
      else setStep('intensity_after');
    };
    backRef.current = () => {
      if (pointIdx > 0) setPointIdx((i) => i - 1);
      else setStep('affirmation');
    };
  }, [pointIdx, points.length]);

  // Start/stop speech recognition based on step + toggle.
  useEffect(() => {
    if (!voiceSupported) return;
    const stop = () => { try { recogRef.current?.stop(); } catch {} recogRef.current = null; setListening(false); };
    if (step !== 'tapping' || !voiceOn) { stop(); return; }

    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const r = new SR();
    r.continuous = true; r.interimResults = false; r.lang = 'en-US';
    const restart = () => {
      if (voiceOnRef.current && stepRef.current === 'tapping' && recogRef.current === r) {
        // Small delay avoids "recognition already started" races in Chrome.
        setTimeout(() => {
          try { r.start(); } catch {}
        }, 300);
      }
    };
    r.onresult = (e: any) => {
      const t = String(e.results[e.results.length - 1][0].transcript || '').toLowerCase().trim();
      if (/\b(next|forward|continue|proceed|go on)\b/.test(t)) advanceRef.current();
      else if (/\b(back|previous|prev|go back)\b/.test(t)) backRef.current();
    };
    // Chrome stops continuous recognition after a short silence — keep it alive.
    r.onend = restart;
    r.onerror = (ev: any) => {
      const err = ev?.error;
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        setVoiceOn(false);
        showAlert('Microphone blocked', 'Allow microphone access in your browser to use hands-free voice commands.');
      }
      // 'no-speech' / 'aborted' / 'network' — onend fires next and restarts.
    };
    recogRef.current = r;
    try { r.start(); setListening(true); } catch {}
    return () => stop();
  }, [step, voiceOn, voiceSupported]);


  const exitToHub = () => {
    router.canGoBack?.() ? router.back() : router.replace('/tools/emotional-gatekeeper' as any);
  };

  // Step-aware back: move to the previous step within the wizard; only leave
  // the screen when on the very first step.
  const handleBack = () => {
    if (showSafety) { setShowSafety(false); return; }
    switch (step) {
      case 'type': exitToHub(); break;
      case 'subject': setStep('type'); break;
      case 'intensity_before': setStep('subject'); break;
      case 'affirmation': setStep('intensity_before'); break;
      case 'tapping':
        if (pointIdx > 0) setPointIdx((i) => i - 1);
        else setStep('affirmation');
        break;
      case 'intensity_after':
        setPointIdx(Math.max(0, points.length - 1));
        setStep('tapping');
        break;
      case 'result': setStep('intensity_after'); break;
      default: exitToHub();
    }
  };

  const checkSafety = (text: string): boolean => {
    const kws = config?.safety_keywords || [];
    const low = text.toLowerCase();
    return kws.some((k) => low.includes((k || '').toLowerCase()));
  };

  const onSubjectContinue = () => {
    if (!subjectText.trim()) {
      showAlert('One step', 'Please share the emotion or problem you want to work on.');
      return;
    }
    if (checkSafety(subjectText)) {
      setSafetyFlagged(true);
      setShowSafety(true);
      return;
    }
    setStep('intensity_before');
  };

  const saveSession = useCallback(async (opts?: { final?: number | null; withReflection?: boolean }) => {
    const sid = await ensureSession();
    if (!sid || !selectedType) return false;
    setSaving(true);
    try {
      await api.post(`/emotional-gatekeeper/eft/${sid}/save`, {
        selected_type: selectedType,
        subject_text: subjectText.trim(),
        affirmation,
        initial_intensity_score: initialIntensity ?? 0,
        final_intensity_score: opts?.final !== undefined ? opts.final : finalIntensity,
        rounds_completed: rounds,
        user_reflection: opts?.withReflection ? reflection : undefined,
        safety_flagged: safetyFlagged,
      });
      return true;
    } catch {
      showAlert('Error', 'Could not save your session. Please try again.');
      return false;
    } finally {
      setSaving(false);
    }
  }, [ensureSession, selectedType, subjectText, affirmation, initialIntensity, finalIntensity, rounds, reflection, safetyFlagged]);

  const onFinalRated = async () => {
    if (finalIntensity === null) {
      showAlert('One step', 'Please rate the intensity from 0 to 10.');
      return;
    }
    await saveSession({ final: finalIntensity });
    setStep('result');
  };

  const repeatRound = () => {
    setRounds((r) => r + 1);
    setFinalIntensity(null);
    setPointIdx(0);
    setStep('tapping');
  };

  const exitFlow = async (withReflection: boolean) => {
    if (withReflection) await saveSession({ final: finalIntensity, withReflection: true });
    router.replace('/tools/emotional-gatekeeper' as any);
  };

  // ---------- progress header ----------
  const mainStepNum = step === 'result' ? 6 : (MAIN_STEPS.indexOf(step) + 1);
  const progressLabel = step === 'tapping'
    ? `Tapping Point ${pointIdx + 1} of ${points.length}`
    : step === 'result' ? 'Complete' : `Step ${mainStepNum} of 6`;

  if (loading || !config) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={EFT.teal} />
          <Text style={styles.loadingText}>Preparing your calm space…</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={[EFT.teal, EFT.tealDark]} style={styles.header}>
        <View style={styles.headerTop}>
          <TouchableOpacity style={styles.backBtn} onPress={handleBack} testID="eft-back">
            <Ionicons name="arrow-back" size={20} color="#FFF" />
          </TouchableOpacity>
          <View style={styles.progressPill}>
            <Text style={styles.progressTxt}>{progressLabel}</Text>
          </View>
        </View>
        <Text style={styles.headerTitle}>{config.title}</Text>
      </LinearGradient>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* ===== SAFETY INTERSTITIAL ===== */}
          {showSafety && (
            <View style={styles.safetyCard} testID="eft-safety-card">
              <Ionicons name="heart" size={26} color={EFT.red} />
              <Text style={styles.safetyText}>{config.safety_message}</Text>
              <TouchableOpacity
                style={styles.safetyBtn}
                onPress={() => { setShowSafety(false); setStep('intensity_before'); }}
                testID="eft-safety-continue"
              >
                <Text style={styles.safetyBtnTxt}>I understand — continue gently</Text>
              </TouchableOpacity>
            </View>
          )}

          {!showSafety && (
            <>
              {/* ===== STEP 1: TYPE ===== */}
              {step === 'type' && (
                <View>
                  <Text style={styles.q}>What would you like to work on now?</Text>
                  {([['emotion', 'An Emotion', 'e.g. stress, fear, anger, sadness, anxiety'],
                     ['problem', 'A Problem / Situation', 'e.g. worry about business, money, a decision']] as const).map(([val, label, hint]) => (
                    <TouchableOpacity
                      key={val}
                      testID={`eft-type-${val}`}
                      style={[styles.radioCard, selectedType === val && styles.radioCardActive]}
                      onPress={() => setSelectedType(val)}
                      activeOpacity={0.8}
                    >
                      <Ionicons
                        name={selectedType === val ? 'radio-button-on' : 'radio-button-off'}
                        size={22} color={selectedType === val ? EFT.tealDark : COLORS.textMuted}
                      />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.radioLabel}>{label}</Text>
                        <Text style={styles.radioHint}>{hint}</Text>
                      </View>
                    </TouchableOpacity>
                  ))}
                  <PrimaryBtn
                    label="Continue" testID="eft-type-continue" disabled={!selectedType}
                    onPress={() => setStep('subject')}
                  />
                </View>
              )}

              {/* ===== STEP 2: SUBJECT ===== */}
              {step === 'subject' && (
                <View>
                  <Text style={styles.q}>
                    {selectedType === 'emotion'
                      ? 'Mention the emotion you are feeling.'
                      : 'Briefly mention the problem or situation troubling you.'}
                  </Text>
                  <TextInput
                    testID="eft-subject-input"
                    style={styles.textArea}
                    placeholder={selectedType === 'emotion'
                      ? 'Stress, Fear, Anger, Sadness, Anxiety, Overwhelm…'
                      : 'I am worried about my business…'}
                    placeholderTextColor={COLORS.textMuted}
                    value={subjectText}
                    onChangeText={(t) => t.length <= 300 && setSubjectText(t)}
                    multiline
                    maxLength={300}
                  />
                  <Text style={styles.charCount}>{subjectText.length}/300</Text>
                  <PrimaryBtn label="Continue" testID="eft-subject-continue" onPress={onSubjectContinue} />
                </View>
              )}

              {/* ===== STEP 3: INTENSITY BEFORE ===== */}
              {step === 'intensity_before' && (
                <View>
                  <Text style={styles.q}>On a scale of 0 to 10, how intense does this feel right now?</Text>
                  <IntensityScale value={initialIntensity} onChange={setInitialIntensity} testIDPrefix="eft-before" />
                  <PrimaryBtn
                    label="Continue" testID="eft-before-continue" disabled={initialIntensity === null}
                    onPress={() => { saveSession(); setStep('affirmation'); }}
                  />
                </View>
              )}

              {/* ===== STEP 4: AFFIRMATION + MEDIA ===== */}
              {step === 'affirmation' && (
                <View>
                  <Text style={styles.q}>Your Setup Affirmation</Text>
                  <View style={styles.affirmCard}>
                    <Ionicons name="sparkles" size={20} color={EFT.tealDark} />
                    <Text style={styles.affirmText}>“{affirmation}”</Text>
                  </View>
                  <Text style={styles.instruction}>
                    Repeat this affirmation 3 times while gently tapping on the Karate Chop point.
                  </Text>

                  <View style={styles.tipBox}>
                    <Text style={styles.tipText}>{config.tapping_instructions}</Text>
                  </View>

                  {/* Diagram */}
                  {!!config.diagram_image_url && (
                    <View style={styles.mediaBlock}>
                      <Text style={styles.mediaLabel}>Tapping Points Diagram</Text>
                      <Image
                        source={{ uri: config.diagram_image_url.startsWith('/') ? `${BACKEND}${config.diagram_image_url}` : config.diagram_image_url }}
                        style={styles.diagram}
                        resizeMode="contain"
                      />
                    </View>
                  )}

                  {/* Video */}
                  {!!config.video_url && (
                    <View style={styles.mediaBlock}>
                      <Text style={styles.mediaLabel}>Guided Tapping Video</Text>
                      {videoFailed ? (
                        <View style={styles.videoFallback}>
                          <Ionicons name="videocam-off" size={22} color={COLORS.textMuted} />
                          <Text style={styles.videoFallbackTxt}>
                            Video is currently unavailable. You can continue using the step-by-step tapping guide below.
                          </Text>
                        </View>
                      ) : (
                        <View style={styles.videoWrap}>
                          <MediaEmbed url={config.video_url} onError={() => setVideoFailed(true)} />
                        </View>
                      )}
                      <Text style={styles.videoHint}>
                        If the video shows a privacy/“cannot be played here” message, it is restricted by its host. You can still follow the step-by-step guide below.
                      </Text>
                    </View>
                  )}

                  <PrimaryBtn
                    label={rounds > 1 ? 'Start Tapping Round Again' : 'Start EFT Tapping'}
                    testID="eft-start-tapping"
                    onPress={() => { setPointIdx(0); setStep('tapping'); }}
                  />
                </View>
              )}

              {/* ===== STEP 5: TAPPING POINTS ===== */}
              {step === 'tapping' && points[pointIdx] && (
                <View>
                  {/* Visual: per-point image if admin provided one, else the full diagram */}
                  {(() => {
                    const img = points[pointIdx].image_url || config.diagram_image_url;
                    if (!img) return null;
                    return (
                      <Image
                        source={{ uri: img.startsWith('/') ? `${BACKEND}${img}` : img }}
                        style={styles.pointImage}
                        resizeMode="contain"
                      />
                    );
                  })()}

                  <View style={styles.pointBadge}>
                    <Text style={styles.pointBadgeTxt}>{pointIdx + 1}</Text>
                  </View>
                  <Text style={styles.pointName}>{points[pointIdx].name}</Text>
                  <Text style={styles.pointInstruction}>{points[pointIdx].instruction}</Text>

                  <View style={styles.reminderCard}>
                    <Text style={styles.reminderLabel}>Say{points[pointIdx].is_setup ? ' (3 times)' : ''}:</Text>
                    <Text style={styles.reminderPhrase}>
                      {points[pointIdx].is_setup ? `“${affirmation}”` : `“${reminderPhrase}”`}
                    </Text>
                  </View>

                  {/* Hands-free voice control (web only) */}
                  {voiceSupported && (
                    <TouchableOpacity
                      testID="eft-voice-toggle"
                      style={[styles.voiceToggle, voiceOn && styles.voiceToggleOn]}
                      onPress={() => setVoiceOn((v) => !v)}
                      activeOpacity={0.8}
                    >
                      <Ionicons name={voiceOn ? 'mic' : 'mic-off'} size={18} color={voiceOn ? '#FFF' : EFT.tealDark} />
                      <Text style={[styles.voiceToggleTxt, voiceOn && { color: '#FFF' }]}>
                        {voiceOn ? (listening ? 'Listening… say “Next” or “Back”' : 'Voice on — starting…') : 'Hands-free: tap to enable voice'}
                      </Text>
                    </TouchableOpacity>
                  )}

                  {pointIdx < points.length - 1 ? (
                    <PrimaryBtn label="Next Point" testID="eft-next-point" onPress={() => advanceRef.current()} />
                  ) : (
                    <PrimaryBtn label="Complete Round" testID="eft-complete-round" onPress={() => advanceRef.current()} />
                  )}

                  {pointIdx > 0 && (
                    <TouchableOpacity style={styles.prevPointBtn} onPress={() => backRef.current()}>
                      <Text style={styles.prevPointTxt}>Previous point</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {/* ===== STEP 6: INTENSITY AFTER ===== */}
              {step === 'intensity_after' && (
                <View>
                  <Text style={styles.q}>Now, again rate the intensity from 0 to 10.</Text>
                  <IntensityScale value={finalIntensity} onChange={setFinalIntensity} testIDPrefix="eft-after" />
                  <PrimaryBtn
                    label={saving ? 'Saving…' : 'See Result'} testID="eft-after-continue"
                    disabled={finalIntensity === null || saving} onPress={onFinalRated}
                  />
                </View>
              )}

              {/* ===== RESULT ===== */}
              {step === 'result' && finalIntensity !== null && (
                <ResultScreen
                  finalIntensity={finalIntensity}
                  initialIntensity={initialIntensity ?? 0}
                  reflection={reflection}
                  setReflection={setReflection}
                  saving={saving}
                  onRepeat={repeatRound}
                  onSaveExit={() => exitFlow(true)}
                  onReturn={() => exitFlow(true)}
                />
              )}

              {/* Disclaimer footer (always present, subtle) */}
              {step !== 'result' && (
                <Text style={styles.disclaimer}>{config.disclaimer}</Text>
              )}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ---------- Result screen ----------
function ResultScreen({ finalIntensity, initialIntensity, reflection, setReflection, saving, onRepeat, onSaveExit, onReturn }: {
  finalIntensity: number; initialIntensity: number; reflection: string;
  setReflection: (s: string) => void; saving: boolean;
  onRepeat: () => void; onSaveExit: () => void; onReturn: () => void;
}) {
  let band: 'low' | 'mid' | 'high' = finalIntensity <= 2 ? 'low' : finalIntensity <= 6 ? 'mid' : 'high';
  const cfg = {
    low: { color: EFT.green, icon: 'happy' as const, msg: 'Beautiful. The emotional intensity has reduced well. Take a slow breath and notice how you feel now.' },
    mid: { color: EFT.amber, icon: 'leaf' as const, msg: 'There is some relief, and a little intensity is still present. You may repeat one more tapping round.' },
    high: { color: EFT.red, icon: 'heart' as const, msg: 'This still feels intense. Please be gentle with yourself. You can repeat the tapping round, and if this feels overwhelming, consider speaking to a trusted person or qualified professional.' },
  }[band];
  const reduction = initialIntensity - finalIntensity;

  return (
    <View>
      <View style={[styles.resultCard, { borderColor: cfg.color }]} testID={`eft-result-${band}`}>
        <Ionicons name={cfg.icon} size={40} color={cfg.color} />
        <View style={styles.scoreRow}>
          <ScorePill label="Before" value={initialIntensity} color={COLORS.textMuted} />
          <Ionicons name="arrow-forward" size={18} color={COLORS.textMuted} />
          <ScorePill label="Now" value={finalIntensity} color={cfg.color} />
          {reduction > 0 && <ScorePill label="Released" value={`-${reduction}`} color={EFT.green} />}
        </View>
        <Text style={styles.resultMsg}>{cfg.msg}</Text>
      </View>

      <Text style={styles.reflectQ}>What do you notice now? <Text style={styles.optional}>(optional)</Text></Text>
      <TextInput
        testID="eft-reflection-input"
        style={styles.textArea}
        placeholder="I feel lighter / calmer / I got a new insight…"
        placeholderTextColor={COLORS.textMuted}
        value={reflection}
        onChangeText={(t) => t.length <= 500 && setReflection(t)}
        multiline
        maxLength={500}
      />
      <Text style={styles.charCount}>{reflection.length}/500</Text>

      {band === 'low' ? (
        <>
          <PrimaryBtn label={saving ? 'Saving…' : 'Save Reflection'} testID="eft-save-reflection" disabled={saving} onPress={onSaveExit} />
          <SecondaryBtn label="Return to Emotional Gatekeepers" testID="eft-return" onPress={onReturn} />
        </>
      ) : (
        <>
          <PrimaryBtn label="Repeat Tapping Round" testID="eft-repeat-round" onPress={onRepeat} />
          <SecondaryBtn label={saving ? 'Saving…' : 'Save and Exit'} testID="eft-save-exit" onPress={onSaveExit} />
        </>
      )}
    </View>
  );
}

function ScorePill({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <View style={styles.scorePill}>
      <Text style={[styles.scoreVal, { color }]}>{value}</Text>
      <Text style={styles.scoreLabel}>{label}</Text>
    </View>
  );
}

// ---------- 0..10 intensity scale ----------
function IntensityScale({ value, onChange, testIDPrefix }: { value: number | null; onChange: (n: number) => void; testIDPrefix: string }) {
  return (
    <View style={styles.scaleWrap}>
      <View style={styles.scaleRow}>
        {Array.from({ length: 11 }, (_, i) => i).map((n) => (
          <TouchableOpacity
            key={n}
            testID={`${testIDPrefix}-${n}`}
            style={[styles.scaleDot, value === n && styles.scaleDotActive]}
            onPress={() => onChange(n)}
          >
            <Text style={[styles.scaleNum, value === n && styles.scaleNumActive]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.scaleLabels}>
        <Text style={styles.scaleEnd}>0 · No intensity</Text>
        <Text style={styles.scaleEnd}>Max · 10</Text>
      </View>
    </View>
  );
}

// ---------- buttons ----------
function PrimaryBtn({ label, onPress, disabled, testID }: { label: string; onPress: () => void; disabled?: boolean; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} activeOpacity={0.85} disabled={disabled} onPress={onPress} style={{ marginTop: 20 }}>
      <LinearGradient
        colors={disabled ? ['#CBD5E1', '#94A3B8'] : [EFT.teal, EFT.tealDark]}
        style={styles.primaryBtn}
      >
        <Text style={styles.primaryBtnTxt}>{label}</Text>
      </LinearGradient>
    </TouchableOpacity>
  );
}

function SecondaryBtn({ label, onPress, testID }: { label: string; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} style={styles.secondaryBtn} onPress={onPress} activeOpacity={0.7}>
      <Text style={styles.secondaryBtnTxt}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 14, color: COLORS.textMuted },
  header: { padding: 20, paddingTop: 10, paddingBottom: 20, borderBottomLeftRadius: 24, borderBottomRightRadius: 24 },
  headerTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  progressPill: { backgroundColor: 'rgba(255,255,255,0.22)', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999 },
  progressTxt: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  scroll: { padding: 20, paddingBottom: 80 },

  q: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 18, lineHeight: 28 },

  radioCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1.5, borderColor: COLORS.border },
  radioCardActive: { borderColor: EFT.teal, backgroundColor: EFT.tealLight },
  radioLabel: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  radioHint: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },

  textArea: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, fontSize: 15, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, minHeight: 110, textAlignVertical: 'top' },
  charCount: { fontSize: 11, color: COLORS.textMuted, textAlign: 'right', marginTop: 6 },

  scaleWrap: { marginTop: 4 },
  scaleRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  scaleDot: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#FFF', borderWidth: 1.5, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  scaleDotActive: { backgroundColor: EFT.teal, borderColor: EFT.tealDark },
  scaleNum: { fontSize: 16, fontWeight: '700', color: COLORS.textSecondary },
  scaleNumActive: { color: '#FFF' },
  scaleLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12 },
  scaleEnd: { fontSize: 12, color: COLORS.textMuted, fontWeight: '600' },

  affirmCard: { flexDirection: 'row', gap: 10, backgroundColor: EFT.tealLight, borderRadius: 14, padding: 18, borderWidth: 1, borderColor: '#99F6E4' },
  affirmText: { flex: 1, fontSize: 17, fontWeight: '700', color: EFT.tealDark, lineHeight: 25, fontStyle: 'italic' },
  instruction: { fontSize: 14, color: COLORS.textSecondary, marginTop: 14, lineHeight: 21 },
  tipBox: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginTop: 14, borderLeftWidth: 3, borderLeftColor: EFT.teal },
  tipText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20 },

  mediaBlock: { marginTop: 20 },
  mediaLabel: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  diagram: { width: '100%', height: 280, borderRadius: 14, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border },
  videoWrap: { borderRadius: 14, overflow: 'hidden', backgroundColor: '#000', height: 210 },
  video: { flex: 1, backgroundColor: '#000' },
  videoFallback: { backgroundColor: '#FFF', borderRadius: 14, padding: 18, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: COLORS.border },
  videoFallbackTxt: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', lineHeight: 20 },
  videoHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 8, lineHeight: 16, fontStyle: 'italic' },

  pointBadge: { width: 56, height: 56, borderRadius: 28, backgroundColor: EFT.teal, justifyContent: 'center', alignItems: 'center', alignSelf: 'center', marginBottom: 16 },
  pointImage: { width: '100%', height: 220, borderRadius: 14, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border, marginBottom: 16 },
  voiceToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 16, paddingVertical: 12, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1.5, borderColor: EFT.teal, backgroundColor: EFT.tealLight },
  voiceToggleOn: { backgroundColor: EFT.teal, borderColor: EFT.tealDark },
  voiceToggleTxt: { fontSize: 13, fontWeight: '700', color: EFT.tealDark },
  pointBadgeTxt: { fontSize: 24, fontWeight: '800', color: '#FFF' },
  pointName: { fontSize: 24, fontWeight: '800', color: COLORS.textPrimary, textAlign: 'center' },
  pointInstruction: { fontSize: 15, color: COLORS.textSecondary, textAlign: 'center', marginTop: 12, lineHeight: 23 },
  reminderCard: { backgroundColor: EFT.tealLight, borderRadius: 14, padding: 18, marginTop: 20, alignItems: 'center', borderWidth: 1, borderColor: '#99F6E4' },
  reminderLabel: { fontSize: 12, color: EFT.tealDark, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  reminderPhrase: { fontSize: 18, fontWeight: '700', color: EFT.tealDark, marginTop: 6, textAlign: 'center', fontStyle: 'italic' },
  prevPointBtn: { marginTop: 14, alignItems: 'center' },
  prevPointTxt: { fontSize: 13, color: COLORS.textMuted, fontWeight: '600' },

  resultCard: { backgroundColor: '#FFF', borderRadius: 18, padding: 22, alignItems: 'center', borderWidth: 2 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 14 },
  scorePill: { alignItems: 'center' },
  scoreVal: { fontSize: 26, fontWeight: '800' },
  scoreLabel: { fontSize: 11, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },
  resultMsg: { fontSize: 15, color: COLORS.textSecondary, textAlign: 'center', marginTop: 16, lineHeight: 23 },
  reflectQ: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 24, marginBottom: 10 },
  optional: { fontSize: 13, color: COLORS.textMuted, fontWeight: '400' },

  primaryBtn: { paddingVertical: 16, borderRadius: 14, alignItems: 'center' },
  primaryBtnTxt: { color: '#FFF', fontSize: 16, fontWeight: '800' },
  secondaryBtn: { paddingVertical: 14, borderRadius: 14, alignItems: 'center', marginTop: 10 },
  secondaryBtnTxt: { color: COLORS.textSecondary, fontSize: 15, fontWeight: '600' },

  safetyCard: { backgroundColor: '#FEF2F2', borderRadius: 16, padding: 22, alignItems: 'center', gap: 12, borderWidth: 1, borderColor: '#FECACA' },
  safetyText: { fontSize: 15, color: '#991B1B', textAlign: 'center', lineHeight: 23 },
  safetyBtn: { backgroundColor: EFT.red, paddingVertical: 14, paddingHorizontal: 20, borderRadius: 12, marginTop: 6 },
  safetyBtnTxt: { color: '#FFF', fontSize: 15, fontWeight: '700' },

  disclaimer: { fontSize: 11, color: COLORS.textMuted, lineHeight: 17, marginTop: 28, fontStyle: 'italic' },
});
