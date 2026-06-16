import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { VoiceInput } from '../../src/components/VoiceInput';
import { VoiceTextInput } from '../../src/components/VoiceTextInput';
import VentToOutletsBanner from '../../src/components/VentToOutletsBanner';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import api from '../../src/utils/api';
import { handleAiError } from '../../src/utils/aiErrors';
import { confirmAiSpend, useAiEstimate } from '../../src/utils/aiEstimates';
import { AiCreditsBadge } from '../../src/components/AiCreditsBadge';
import { Alert } from '../../src/utils/crossAlert';

const LOOP_AUDIO_URL = 'https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/qgkdw529_Breaking%20the%20LOOP.mp3';

const LOOP_SCRIPT = `A thought keeps coming to your mind again and again — like a broken record. You are looping. This happens because the mind cannot accept uncertainty. It keeps replaying the same scenario, hoping to find a resolution that may never come.

The 4 powerful methods to break this loop:

1. "I Don't Know" — Accept uncertainty. Stop labeling things as good or bad. When you truly say "I don't know," the mind stops its frantic search for answers and the loop weakens.

2. "All Is Well" — Trust life's goodness. Find the silver lining. When you affirm that all is well, you shift from anxiety to trust, and the repeating thought loses its grip.

3. "Both Good and Bad" — See the duality. Every situation carries both aspects. When you hold both perspectives simultaneously, the mind stops fixating on just one side.

4. "This Too Shall Pass" — Recognize impermanence. Nothing — absolutely nothing — lasts forever. When you see the temporary nature of this thought, it naturally fades.

Choose the method that resonates most. Answer the reflection questions honestly. Let the loop dissolve.`;

const METHODS = [
  { id: 'i_dont_know', name: "I Don't Know", icon: 'help-circle' as const, color: '#6366F1',
    desc: 'Accept uncertainty. Stop labeling good or bad.',
    questions: ['What are you sure about in this situation?', 'What are you NOT sure about?', 'Can you accept not knowing the full truth right now?'] },
  { id: 'all_is_well', name: 'All Is Well', icon: 'sunny' as const, color: '#F59E0B',
    desc: 'Trust life\'s goodness. Find the silver lining.',
    questions: ['What could go RIGHT in this situation?', 'What hidden opportunity might exist here?', 'Can you trust that things can work out?'] },
  { id: 'both_good_bad', name: 'Both Good and Bad', icon: 'git-compare' as const, color: '#10B981',
    desc: 'See duality. Every situation has both aspects.',
    questions: ['What is the POSITIVE side of this situation?', 'What is the NEGATIVE side?', 'Can both exist at the same time?'] },
  { id: 'this_too_shall_pass', name: 'This Too Shall Pass', icon: 'hourglass' as const, color: '#8B5CF6',
    desc: 'Recognize impermanence. Nothing lasts forever.',
    questions: ['How will you feel about this in 1 week?', 'How about in 1 month?', 'And in 1 year from now?'] },
];

export default function EGLoopScreen() {
  const router = useRouter();
  const goBack = () => {
    if (params.return_to === 'solution-finder' && params.return_id) {
      router.replace(`/tools/solution-finder?id=${params.return_id}&step=2` as any);
      return;
    }
    if (router.canGoBack?.()) router.back();
    else router.replace('/tools/emotional-gatekeeper' as any);
  };
  const params = useLocalSearchParams<{ sessionId: string; return_to?: string; return_id?: string }>();
  const sessionId = params.sessionId;
  const [step, setStep] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ y: 0, animated: false }); }, [step]);
  const [loading, setLoading] = useState(false);
  const [guideExpanded, setGuideExpanded] = useState(false);

  // Step 0: Capture
  const [repeatedThought, setRepeatedThought] = useState('');
  const [emotion, setEmotion] = useState('');
  const [repeatCount, setRepeatCount] = useState(3);
  const [fear, setFear] = useState('');
  const [tryingToSolve, setTryingToSolve] = useState('');

  // Step 1: AI recommendation
  const [recommendation, setRecommendation] = useState<any>(null);
  const [selectedMethod, setSelectedMethod] = useState('');

  // Step 2: Method answers
  const [answers, setAnswers] = useState<Record<string, string>>({});

  // Step 3: Reframe
  const [reframe, setReframe] = useState<any>(null);

  // Resume an in-progress/completed session: prefill inputs and jump to the right step.
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const { data } = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
        const l = data?.loop_reflection;
        if (!l) return;
        if (l.repeated_thought) setRepeatedThought(l.repeated_thought);
        if (l.emotion) setEmotion(l.emotion);
        if (typeof l.repeat_count_today === 'number') setRepeatCount(l.repeat_count_today);
        if (l.fear) setFear(l.fear);
        if (l.trying_to_solve) setTryingToSolve(l.trying_to_solve);
        if (l.ai_recommended_method) setRecommendation(l.ai_recommended_method);
        if (l.selected_method) setSelectedMethod(l.selected_method);
        if (l.method_answers) setAnswers(l.method_answers);
        const rf = l.ai_reframe_full;
        if (rf && typeof rf === 'object') { setReframe(rf); setStep(2); }
        else if (l.ai_recommended_method) setStep(1);
      } catch { /* ignore */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const loopRecEst = useAiEstimate('eg_loop_recommend');
  const loopRefEst = useAiEstimate('eg_loop_reframe');

  const handleCapture = async () => {
    if (!(await confirmAiSpend('eg_loop_recommend', 'Loop recommendation'))) return;
    if (!repeatedThought.trim()) { Alert.alert('Required', 'Describe the repeating thought.'); return; }
    setLoading(true);
    try {
      await api.post(`/emotional-gatekeeper/loop/${sessionId}/capture`, {
        repeated_thought: repeatedThought, emotion, repeat_count_today: repeatCount,
        fear, trying_to_solve: tryingToSolve,
      });
      const res = await api.post(`/emotional-gatekeeper/loop/${sessionId}/recommend`);
      setRecommendation(res.data.recommendation);
      if (res.data.recommendation?.recommended_method) {
        setSelectedMethod(res.data.recommendation.recommended_method);
      }
      setStep(1);
    } catch (err) { await handleAiError(err, { router, retry: handleCapture }); }
    finally { setLoading(false); }
  };

  const handleMethodSubmit = async () => {
    if (!(await confirmAiSpend('eg_loop_reframe', 'Loop reframe'))) return;
    if (!selectedMethod) { Alert.alert('Required', 'Select a method.'); return; }
    setLoading(true);
    try {
      await api.put(`/emotional-gatekeeper/loop/${sessionId}/method`, {
        selected_method: selectedMethod, method_answers: answers,
      });
      const res = await api.post(`/emotional-gatekeeper/loop/${sessionId}/reframe`);
      setReframe(res.data.reframe);
      setStep(2);
    } catch (err) { await handleAiError(err, { router, retry: handleMethodSubmit }); }
    finally { setLoading(false); }
  };

  const methodObj = METHODS.find(m => m.id === selectedMethod);

  const renderAudioGuide = () => (
    <View style={s.audioGuideContainer}>
      <TouchableOpacity
        style={s.audioGuideHeader}
        onPress={() => setGuideExpanded(!guideExpanded)}
        activeOpacity={0.7}
      >
        <View style={s.audioGuideIcon}>
          <Ionicons name="headset" size={20} color="#8B5CF6" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.audioGuideTitle}>Audio Guide: Breaking the Loop</Text>
          <Text style={s.audioGuideSub}>Listen to the guided briefing before you begin</Text>
        </View>
        <Ionicons name={guideExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#8B5CF6" />
      </TouchableOpacity>
      {guideExpanded && (
        <View style={s.audioGuideBody}>
          <AudioGuidePlayer
            uri={LOOP_AUDIO_URL}
            title="Breaking the LOOP — Guided Audio"
            color="#8B5CF6"
          />
          <View style={s.scriptBox}>
            <View style={s.scriptHeader}>
              <Ionicons name="document-text" size={16} color="#7C3AED" />
              <Text style={s.scriptLabel}>Briefing Script</Text>
            </View>
            <Text style={s.scriptText}>{LOOP_SCRIPT}</Text>
          </View>
        </View>
      )}
    </View>
  );

  const renderStep0 = () => (
    <View style={s.stepContent}>
      {renderAudioGuide()}
      <Text style={s.stepTitle}>What thought keeps repeating in your mind?</Text>
      <View style={s.inputRow}>
        <VoiceTextInput inputStyle={s.textArea} multiline placeholder="The thought I keep having..."
          value={repeatedThought} onChangeText={setRepeatedThought} placeholderTextColor={COLORS.textMuted}
          sessionId={sessionId || ''} field="repeated_thought" color="#8B5CF6" />
      </View>
      <Text style={s.label}>What emotion comes with it?</Text>
      <VoiceTextInput inputStyle={s.input} placeholder="e.g., anxiety, frustration, fear..."
        value={emotion} onChangeText={setEmotion} placeholderTextColor={COLORS.textMuted}
        sessionId={sessionId || ''} field="emotion" color="#8B5CF6" />
      <Text style={s.label}>Times repeated today: {repeatCount}</Text>
      <View style={s.countRow}>
        <TouchableOpacity style={s.countBtn} onPress={() => setRepeatCount(Math.max(1, repeatCount - 1))}>
          <Ionicons name="remove" size={18} color="#8B5CF6" />
        </TouchableOpacity>
        <Text style={s.countNum}>{repeatCount}</Text>
        <TouchableOpacity style={s.countBtn} onPress={() => setRepeatCount(repeatCount + 1)}>
          <Ionicons name="add" size={18} color="#8B5CF6" />
        </TouchableOpacity>
      </View>
      <Text style={s.label}>What fear is behind this?</Text>
      <VoiceTextInput inputStyle={s.input} placeholder="I'm afraid that..."
        value={fear} onChangeText={setFear} placeholderTextColor={COLORS.textMuted}
        sessionId={sessionId || ''} field="fear" color="#8B5CF6" />
      <Text style={s.label}>What are you trying to solve by replaying?</Text>
      <VoiceTextInput inputStyle={s.input} placeholder="I keep thinking because..."
        value={tryingToSolve} onChangeText={setTryingToSolve} placeholderTextColor={COLORS.textMuted}
        sessionId={sessionId || ''} field="trying_to_solve" color="#8B5CF6" />
      <TouchableOpacity style={s.nextBtn} onPress={handleCapture} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Get AI Recommendation{loopRecEst ? ` · ~${loopRecEst} cr` : ''}</Text><Ionicons name="bulb" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep1 = () => (
    <View style={s.stepContent}>
      {recommendation && (
        <View style={s.recCard}>
          <Ionicons name="bulb" size={20} color="#D97706" />
          <View style={{ flex: 1 }}>
            <Text style={s.recTitle}>AI Recommends: {METHODS.find(m => m.id === recommendation.recommended_method)?.name}</Text>
            <Text style={s.recReason}>{recommendation.reason}</Text>
          </View>
        </View>
      )}
      <Text style={s.stepTitle}>Choose a Loop-Breaking Method</Text>
      {METHODS.map(m => (
        <TouchableOpacity key={m.id} style={[s.methodCard, selectedMethod === m.id && { borderColor: m.color, borderWidth: 2 }]}
          onPress={() => setSelectedMethod(m.id)}>
          <View style={[s.methodIcon, { backgroundColor: m.color }]}>
            <Ionicons name={m.icon} size={24} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.methodName}>{m.name}</Text>
            <Text style={s.methodDesc}>{m.desc}</Text>
          </View>
          {selectedMethod === m.id && <Ionicons name="checkmark-circle" size={22} color={m.color} />}
        </TouchableOpacity>
      ))}
      {selectedMethod && methodObj && (
        <>
          <Text style={[s.sectionTitle, { marginTop: 20 }]}>Answer the Reflections</Text>
          {methodObj.questions.map((q, i) => (
            <View key={i}>
              <Text style={s.label}>{q}</Text>
              <View style={s.inputRow}>
                <VoiceTextInput inputStyle={s.textArea} multiline placeholder="Your reflection..."
                  value={answers[`q${i}`] || ''}
                  onChangeText={(t) => setAnswers(prev => ({ ...prev, [`q${i}`]: t }))}
                  placeholderTextColor={COLORS.textMuted}
                  sessionId={sessionId || ''} field={`q${i}`} color="#8B5CF6" />
              </View>
            </View>
          ))}
        </>
      )}
      <TouchableOpacity style={s.nextBtn} onPress={handleMethodSubmit} disabled={loading || !selectedMethod}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Generate Reframe{loopRefEst ? ` · ~${loopRefEst} cr` : ''}</Text><Ionicons name="sparkles" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep2 = () => (
    <View style={s.stepContent}>
      <LinearGradient colors={['#EDE9FE', '#DDD6FE']} style={s.reframeCard}>
        <Text style={s.reframeTitle}>Loop Reframe</Text>
        {reframe && (
          <>
            <Text style={s.rfLabel}>Original Thought</Text>
            <Text style={s.rfText}>{reframe.original_thought}</Text>
            <Text style={s.rfLabel}>Emotional Driver</Text>
            <Text style={s.rfText}>{reframe.emotional_driver}</Text>
            <Text style={s.rfLabel}>Method Applied</Text>
            <Text style={s.rfText}>{reframe.method_applied}</Text>
            <View style={s.rfHighlight}>
              <Ionicons name="sparkles" size={18} color="#7C3AED" />
              <Text style={s.rfHighlightText}>{reframe.new_perspective}</Text>
            </View>
            <View style={s.calmBox}>
              <Ionicons name="heart" size={16} color="#059669" />
              <Text style={s.calmText}>{reframe.calming_statement}</Text>
            </View>
            <View style={s.actionBox}>
              <Ionicons name="flash" size={16} color="#D97706" />
              <Text style={s.actionText}>{reframe.immediate_action}</Text>
            </View>
            <View style={s.affirmBox}>
              <Text style={s.affirmText}>&ldquo;{reframe.reflection_affirmation}&rdquo;</Text>
            </View>
            {reframe.deeper_limitation_detected && (
              <TouchableOpacity style={s.limitBtn}
                onPress={() => router.push(`/tools/eg-limitation?sessionId=${sessionId}` as any)}>
                <Ionicons name="lock-open" size={16} color="#FFF" />
                <Text style={s.limitBtnText}>Deeper Limitation Detected — Explore</Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </LinearGradient>
      <TouchableOpacity
        style={s.altBtn}
        onPress={() => router.push(`/tools/eg-advisor?sessionId=${sessionId}` as any)}
      >
        <Ionicons name="leaf-outline" size={16} color="#0EA5E9" />
        <Text style={s.altBtnText}>Effective Outlets Advisor</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.doneBtn} onPress={() => router.push('/tools/emotional-gatekeeper' as any)}>
        <Text style={s.doneBtnText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <LinearGradient colors={['#8B5CF6', '#7C3AED']} style={s.header}>
          <View style={s.headerTop}>
            <TouchableOpacity style={s.backBtn} onPress={goBack}>
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <AiCreditsBadge compact autoRefresh lowThreshold={loopRefEst ?? undefined} />
          </View>
          <Text style={s.headerTitle}>Breaking the Loop</Text>
          <Text style={s.headerSub}>
            {step === 0 ? 'Capture the Loop' : step === 1 ? 'Choose & Apply Method' : 'Your Reframe'}
          </Text>
        </LinearGradient>
        <ScrollView ref={scrollRef} showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
          <VentToOutletsBanner returnTo={(params as any).return_to} returnId={(params as any).return_id} />
          {step === 0 && renderStep0()}
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { padding: 20, paddingTop: 8, borderBottomLeftRadius: 20, borderBottomRightRadius: 20 },
  headerTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  stepContent: { padding: 16 },
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  label: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 14, marginBottom: 8 },
  input: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  textArea: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, minHeight: 80, textAlignVertical: 'top', flex: 1 },
  inputRow: { gap: 8 },
  countRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 20 },
  countBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#EDE9FE', justifyContent: 'center', alignItems: 'center' },
  countNum: { fontSize: 24, fontWeight: '800', color: '#8B5CF6' },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#8B5CF6', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  recCard: { flexDirection: 'row', gap: 10, backgroundColor: '#FFFBEB', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#FDE68A' },
  recTitle: { fontSize: 14, fontWeight: '700', color: '#92400E' },
  recReason: { fontSize: 12, color: '#78350F', marginTop: 4, lineHeight: 17 },
  methodCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  methodIcon: { width: 48, height: 48, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  methodName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  methodDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  reframeCard: { borderRadius: 16, padding: 20 },
  reframeTitle: { fontSize: 20, fontWeight: '800', color: '#5B21B6', marginBottom: 12 },
  rfLabel: { fontSize: 12, fontWeight: '700', color: '#6D28D9', marginTop: 10, textTransform: 'uppercase' },
  rfText: { fontSize: 14, color: '#4C1D95', marginTop: 2, lineHeight: 20 },
  rfHighlight: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginTop: 16 },
  rfHighlightText: { fontSize: 14, color: '#5B21B6', flex: 1, lineHeight: 20, fontWeight: '500' },
  calmBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#ECFDF5', borderRadius: 10, padding: 12, marginTop: 12 },
  calmText: { fontSize: 13, color: '#065F46', flex: 1 },
  actionBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FFFBEB', borderRadius: 10, padding: 12, marginTop: 8 },
  actionText: { fontSize: 13, color: '#92400E', flex: 1 },
  affirmBox: { backgroundColor: 'rgba(139,92,246,0.1)', borderRadius: 10, padding: 14, marginTop: 12, alignItems: 'center' },
  affirmText: { fontSize: 14, fontWeight: '600', color: '#7C3AED', fontStyle: 'italic', textAlign: 'center' },
  limitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#3B82F6', borderRadius: 12, paddingVertical: 14, marginTop: 16 },
  limitBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
  altBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#FFFFFF', borderColor: '#0EA5E9', borderWidth: 1.5, borderRadius: 14, paddingVertical: 12, marginTop: 14, marginHorizontal: 16 },
  altBtnText: { fontSize: 14, fontWeight: '700', color: '#0EA5E9' },

  // Audio Guide
  audioGuideContainer: { backgroundColor: '#FFF', borderRadius: 14, marginBottom: 16, borderWidth: 1, borderColor: '#EDE9FE', overflow: 'hidden' },
  audioGuideHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14 },
  audioGuideIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#EDE9FE', justifyContent: 'center', alignItems: 'center' },
  audioGuideTitle: { fontSize: 14, fontWeight: '700', color: '#5B21B6' },
  audioGuideSub: { fontSize: 11, color: '#7C3AED', marginTop: 2 },
  audioGuideBody: { paddingHorizontal: 14, paddingBottom: 14 },
  scriptBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 14, marginTop: 10, borderLeftWidth: 3, borderLeftColor: '#8B5CF6' },
  scriptHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  scriptLabel: { fontSize: 12, fontWeight: '700', color: '#7C3AED', textTransform: 'uppercase' },
  scriptText: { fontSize: 13, color: '#475569', lineHeight: 20, fontStyle: 'italic' },
});
