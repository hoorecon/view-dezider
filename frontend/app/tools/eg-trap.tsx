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
import api from '../../src/utils/api';
import { handleAiError } from '../../src/utils/aiErrors';
import { confirmAiSpend, useAiEstimate } from '../../src/utils/aiEstimates';
import { AiCreditsBadge } from '../../src/components/AiCreditsBadge';
import { Alert } from '../../src/utils/crossAlert';
import { safeBack } from '../../src/utils/navigation';

const CATEGORIES = [
  'career', 'business', 'relationship', 'money', 'family',
  'health', 'self_worth', 'spirituality', 'other',
];
const SCAN_PATTERNS = [
  'mistakes', 'risks', 'rejection', 'loss', 'failure',
  'betrayal', 'delay', 'uncertainty',
];

export default function EGTrapScreen() {
  const router = useRouter();
  const goBack = () => {
    if (params.return_to === 'solution-finder' && params.return_id) {
      router.replace(`/tools/solution-finder?id=${params.return_id}&step=2` as any);
      return;
    }
    if (router.canGoBack?.()) safeBack(router);
    else router.replace('/tools/emotional-gatekeeper' as any);
  };
  const params = useLocalSearchParams<{ sessionId: string; return_to?: string; return_id?: string }>();
  const sessionId = params.sessionId;
  const [step, setStep] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ y: 0, animated: false }); }, [step]);
  const [loading, setLoading] = useState(false);

  // Step 1: Capture
  const [situation, setSituation] = useState('');
  const [category, setCategory] = useState('');
  const [intensity, setIntensity] = useState(5);

  // Step 2: Landscaping
  const [scanningFor, setScanningFor] = useState('');
  const [scanPatterns, setScanPatterns] = useState<string[]>([]);
  const [noUrgency, setNoUrgency] = useState<boolean | null>(null);
  const [repeatedConcern, setRepeatedConcern] = useState('');

  // Step 3: Linking
  const [triggerType, setTriggerType] = useState<'external' | 'internal' | ''>('');
  const [triggerDesc, setTriggerDesc] = useState('');
  const [linkingMeaning, setLinkingMeaning] = useState('');

  // Step 4: Looping
  const [repeatingThought, setRepeatingThought] = useState('');
  const [gettingNewSolution, setGettingNewSolution] = useState<boolean | null>(null);
  const [emotionIncreasing, setEmotionIncreasing] = useState('');
  const [intensityAfter, setIntensityAfter] = useState(5);

  // Step 5: Analysis result
  const [analysis, setAnalysis] = useState<any>(null);

  // Resume an in-progress/completed session: prefill inputs and jump to the furthest step.
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const { data } = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
        const t = data?.trap_reflection;
        if (!t) return;
        if (t.situation) setSituation(t.situation);
        if (t.category) setCategory(t.category);
        if (typeof t.intensity === 'number') setIntensity(t.intensity);
        if (t.scanning_for) setScanningFor(t.scanning_for);
        if (Array.isArray(t.scanning_patterns)) setScanPatterns(t.scanning_patterns);
        if (typeof t.scanning_without_urgency === 'boolean') setNoUrgency(t.scanning_without_urgency);
        if (t.repeated_concern) setRepeatedConcern(t.repeated_concern);
        if (t.trigger_type) setTriggerType(t.trigger_type);
        if (t.trigger_description) setTriggerDesc(t.trigger_description);
        if (t.linking_meaning) setLinkingMeaning(t.linking_meaning);
        if (t.looping_thought) setRepeatingThought(t.looping_thought);
        if (typeof t.getting_new_solution === 'boolean') setGettingNewSolution(t.getting_new_solution);
        if (t.emotion_increasing) setEmotionIncreasing(t.emotion_increasing);
        if (typeof t.intensity_after_loop === 'number') setIntensityAfter(t.intensity_after_loop);
        const landscapeDone = !!(t.scanning_for || (Array.isArray(t.scanning_patterns) && t.scanning_patterns.length) || t.repeated_concern);
        const linkingDone = !!(t.linking_meaning || t.trigger_description);
        if (t.ai_summary) { setAnalysis(t.ai_summary); setStep(4); }
        else if (t.looping_thought || linkingDone) setStep(3);
        else if (landscapeDone) setStep(2);
        else setStep(1);
      } catch { /* ignore */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const steps = [
    { title: 'Describe the Situation', icon: 'create' },
    { title: 'Landscaping', icon: 'search' },
    { title: 'Linking', icon: 'link' },
    { title: 'Looping', icon: 'sync' },
    { title: 'AI Awareness', icon: 'bulb' },
  ];

  const trapEst = useAiEstimate('eg_trap_analyze');

  const handleCapture = async () => {
    if (!situation.trim()) { Alert.alert('Required', 'Please describe your situation.'); return; }
    setLoading(true);
    try {
      await api.post(`/emotional-gatekeeper/trap/${sessionId}/capture`, {
        situation, category: category || 'other', intensity,
      });
      setStep(1);
    } catch (err) { Alert.alert('Error', 'Failed to save. Try again.'); }
    finally { setLoading(false); }
  };

  const handleLandscaping = async () => {
    setLoading(true);
    try {
      await api.put(`/emotional-gatekeeper/trap/${sessionId}/landscaping`, {
        scanning_for: scanningFor, scanning_patterns: scanPatterns,
        scanning_without_urgency: noUrgency, repeated_concern: repeatedConcern,
      });
      setStep(2);
    } catch (err) { Alert.alert('Error', 'Failed to save.'); }
    finally { setLoading(false); }
  };

  const handleLinking = async () => {
    setLoading(true);
    try {
      await api.put(`/emotional-gatekeeper/trap/${sessionId}/linking`, {
        trigger_description: triggerDesc, trigger_type: triggerType,
        linking_meaning: linkingMeaning,
      });
      setStep(3);
    } catch (err) { Alert.alert('Error', 'Failed to save.'); }
    finally { setLoading(false); }
  };

  const handleLooping = async () => {
    if (!(await confirmAiSpend('eg_trap_analyze', 'Trap analysis'))) return;
    setLoading(true);
    try {
      await api.put(`/emotional-gatekeeper/trap/${sessionId}/looping`, {
        repeating_thought: repeatingThought, getting_new_solution: gettingNewSolution,
        emotion_increasing: emotionIncreasing,
        intensity_before: intensity, intensity_after: intensityAfter,
      });
      // Now get AI analysis
      const res = await api.post(`/emotional-gatekeeper/trap/${sessionId}/analyze`);
      setAnalysis(res.data.analysis);
      setStep(4);
    } catch (err) { await handleAiError(err, { router, retry: handleLooping }); }
    finally { setLoading(false); }
  };

  const renderProgress = () => (
    <View style={s.progressRow}>
      {steps.map((st, i) => (
        <View key={i} style={s.progressItem}>
          <View style={[s.progressDot, i <= step && s.progressDotActive]}>
            {i < step ? <Ionicons name="checkmark" size={12} color="#FFF" /> :
              <Text style={[s.progressDotText, i <= step && { color: '#FFF' }]}>{i + 1}</Text>}
          </View>
          {i < steps.length - 1 && <View style={[s.progressLine, i < step && s.progressLineActive]} />}
        </View>
      ))}
    </View>
  );

  const renderStep0 = () => (
    <View style={s.stepContent}>
      <Text style={s.stepTitle}>What's the situation that's been occupying your mind?</Text>
      <Text style={s.stepHint}>Describe it honestly. No one else will see this.</Text>
      <View style={s.inputRow}>
        <VoiceTextInput inputStyle={s.textArea} multiline placeholder="Describe your situation..."
          value={situation} onChangeText={setSituation} placeholderTextColor={COLORS.textMuted}
          sessionId={sessionId || ''} field="situation" color="#EF4444" />
      </View>
      <Text style={s.label}>Life Area</Text>
      <View style={s.chipRow}>
        {CATEGORIES.map(c => (
          <TouchableOpacity key={c} style={[s.chip, category === c && s.chipActive]}
            onPress={() => setCategory(c)}>
            <Text style={[s.chipText, category === c && s.chipTextActive]}>
              {c.replace('_', ' ')}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.label}>Intensity Level: {intensity}/10</Text>
      <View style={s.sliderRow}>
        {[1,2,3,4,5,6,7,8,9,10].map(n => (
          <TouchableOpacity key={n} style={[s.sliderDot,
            n <= intensity && { backgroundColor: n <= 3 ? '#10B981' : n <= 6 ? '#F59E0B' : '#EF4444' }]}
            onPress={() => setIntensity(n)}>
            <Text style={[s.sliderNum, n <= intensity && { color: '#FFF' }]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TouchableOpacity style={s.nextBtn} onPress={handleCapture} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Next: Landscaping</Text><Ionicons name="arrow-forward" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep1 = () => (
    <View style={s.stepContent}>
      <Text style={s.stepTitle}>Landscaping: Is your mind scanning for problems?</Text>
      <Text style={s.stepHint}>The mind often searches for issues without urgency — just habit.</Text>
      <Text style={s.label}>What is your mind scanning for?</Text>
      <View style={s.inputRow}>
        <VoiceTextInput inputStyle={s.textArea} multiline placeholder="What keeps coming up..."
          value={scanningFor} onChangeText={setScanningFor} placeholderTextColor={COLORS.textMuted}
          sessionId={sessionId || ''} field="scanning_for" color="#EF4444" />
      </View>
      <Text style={s.label}>Scanning Patterns (select all that apply)</Text>
      <View style={s.chipRow}>
        {SCAN_PATTERNS.map(p => (
          <TouchableOpacity key={p}
            style={[s.chip, scanPatterns.includes(p) && s.chipActive]}
            onPress={() => setScanPatterns(prev =>
              prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p])}>
            <Text style={[s.chipText, scanPatterns.includes(p) && s.chipTextActive]}>{p}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.label}>Is this scanning without real urgency?</Text>
      <View style={s.boolRow}>
        <TouchableOpacity style={[s.boolBtn, noUrgency === true && s.boolBtnActive]}
          onPress={() => setNoUrgency(true)}>
          <Text style={[s.boolText, noUrgency === true && s.boolTextActive]}>Yes, no urgency</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.boolBtn, noUrgency === false && s.boolBtnActive]}
          onPress={() => setNoUrgency(false)}>
          <Text style={[s.boolText, noUrgency === false && s.boolTextActive]}>It feels urgent</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.label}>Repeated concern that keeps coming back</Text>
      <VoiceTextInput inputStyle={s.input} placeholder="The thought that keeps returning..."
        value={repeatedConcern} onChangeText={setRepeatedConcern} placeholderTextColor={COLORS.textMuted}
        sessionId={sessionId || ''} field="repeated_concern" color="#EF4444" />
      <TouchableOpacity style={s.nextBtn} onPress={handleLandscaping} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Next: Linking</Text><Ionicons name="arrow-forward" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep2 = () => (
    <View style={s.stepContent}>
      <Text style={s.stepTitle}>Linking: What triggered this concern?</Text>
      <Text style={s.stepHint}>Your mind links a trigger to a problem, creating a chain.</Text>
      <Text style={s.label}>Trigger Type</Text>
      <View style={s.boolRow}>
        <TouchableOpacity style={[s.boolBtn, triggerType === 'external' && s.boolBtnActive]}
          onPress={() => setTriggerType('external')}>
          <Text style={[s.boolText, triggerType === 'external' && s.boolTextActive]}>External</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.boolBtn, triggerType === 'internal' && s.boolBtnActive]}
          onPress={() => setTriggerType('internal')}>
          <Text style={[s.boolText, triggerType === 'internal' && s.boolTextActive]}>Internal</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.label}>Describe the trigger</Text>
      <View style={s.inputRow}>
        <VoiceTextInput inputStyle={s.textArea} multiline placeholder="What happened or what thought came..."
          value={triggerDesc} onChangeText={setTriggerDesc} placeholderTextColor={COLORS.textMuted}
          sessionId={sessionId || ''} field="trigger" color="#EF4444" />
      </View>
      <Text style={s.label}>What meaning did your mind attach to this?</Text>
      <VoiceTextInput inputStyle={s.textArea} multiline placeholder="My mind concluded that..."
        value={linkingMeaning} onChangeText={setLinkingMeaning} placeholderTextColor={COLORS.textMuted}
        sessionId={sessionId || ''} field="linking_meaning" color="#EF4444" />
      <TouchableOpacity style={s.nextBtn} onPress={handleLinking} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Next: Looping</Text><Ionicons name="arrow-forward" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep3 = () => (
    <View style={s.stepContent}>
      <Text style={s.stepTitle}>Looping: Is the thought repeating?</Text>
      <Text style={s.stepHint}>The mind replays issues, creating a false feeling of problem-solving.</Text>
      <Text style={s.label}>The thought that keeps repeating</Text>
      <View style={s.inputRow}>
        <VoiceTextInput inputStyle={s.textArea} multiline placeholder="I keep thinking about..."
          value={repeatingThought} onChangeText={setRepeatingThought} placeholderTextColor={COLORS.textMuted}
          sessionId={sessionId || ''} field="looping" color="#EF4444" />
      </View>
      <Text style={s.label}>Are you getting any new solutions from this replay?</Text>
      <View style={s.boolRow}>
        <TouchableOpacity style={[s.boolBtn, gettingNewSolution === true && s.boolBtnActive]}
          onPress={() => setGettingNewSolution(true)}>
          <Text style={[s.boolText, gettingNewSolution === true && s.boolTextActive]}>Yes</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.boolBtn, gettingNewSolution === false && s.boolBtnActive]}
          onPress={() => setGettingNewSolution(false)}>
          <Text style={[s.boolText, gettingNewSolution === false && s.boolTextActive]}>No, just replaying</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.label}>Is the emotion increasing or decreasing?</Text>
      <View style={s.boolRow}>
        <TouchableOpacity style={[s.boolBtn, emotionIncreasing === 'increasing' && s.boolBtnActive]}
          onPress={() => setEmotionIncreasing('increasing')}>
          <Text style={[s.boolText, emotionIncreasing === 'increasing' && s.boolTextActive]}>Increasing</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.boolBtn, emotionIncreasing === 'decreasing' && s.boolBtnActive]}
          onPress={() => setEmotionIncreasing('decreasing')}>
          <Text style={[s.boolText, emotionIncreasing === 'decreasing' && s.boolTextActive]}>Decreasing</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.boolBtn, emotionIncreasing === 'same' && s.boolBtnActive]}
          onPress={() => setEmotionIncreasing('same')}>
          <Text style={[s.boolText, emotionIncreasing === 'same' && s.boolTextActive]}>Same</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.label}>Intensity After Looping: {intensityAfter}/10</Text>
      <View style={s.sliderRow}>
        {[1,2,3,4,5,6,7,8,9,10].map(n => (
          <TouchableOpacity key={n} style={[s.sliderDot,
            n <= intensityAfter && { backgroundColor: n <= 3 ? '#10B981' : n <= 6 ? '#F59E0B' : '#EF4444' }]}
            onPress={() => setIntensityAfter(n)}>
            <Text style={[s.sliderNum, n <= intensityAfter && { color: '#FFF' }]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TouchableOpacity style={s.nextBtn} onPress={handleLooping} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Get AI Awareness{trapEst ? ` · ~${trapEst} cr` : ''}</Text><Ionicons name="bulb" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep4 = () => (
    <View style={s.stepContent}>
      <LinearGradient colors={['#FEF3C7', '#FDE68A']} style={s.analysisCard}>
        <Text style={s.analysisTitle}>AI Trap Awareness</Text>
        {analysis && (
          <>
            <View style={s.analysisBadge}>
              <Text style={s.analysisBadgeText}>
                Stage: {analysis.current_stage?.toUpperCase()} ({Math.round((analysis.stage_confidence || 0) * 100)}%)
              </Text>
            </View>
            <Text style={s.analysisLabel}>Main Trigger</Text>
            <Text style={s.analysisText}>{analysis.main_trigger}</Text>
            <Text style={s.analysisLabel}>Repeated Thought</Text>
            <Text style={s.analysisText}>{analysis.repeated_thought}</Text>
            <Text style={s.analysisLabel}>How Emotions Are Amplified</Text>
            <Text style={s.analysisText}>{analysis.emotional_amplification_pattern}</Text>
            <Text style={s.analysisLabel}>False Problem-Solving</Text>
            <Text style={s.analysisText}>{analysis.false_problem_solving}</Text>
            <View style={s.awarenessBox}>
              <Ionicons name="bulb" size={20} color="#D97706" />
              <Text style={s.awarenessText}>{analysis.awareness_statement}</Text>
            </View>
            {analysis.intervention && (
              <View style={s.interventionBox}>
                <Text style={s.interventionTitle}>Recommended Intervention</Text>
                <Text style={s.interventionText}>{analysis.intervention.description}</Text>
                <View style={s.actionBox}>
                  <Ionicons name="flash" size={16} color="#059669" />
                  <Text style={s.actionBoxText}>{analysis.intervention.immediate_action}</Text>
                </View>
              </View>
            )}
          </>
        )}
      </LinearGradient>
      <View style={s.btnRow}>
        <TouchableOpacity style={[s.nextBtn, { flex: 1, backgroundColor: '#8B5CF6' }]}
          onPress={() => router.push(`/tools/eg-loop?sessionId=${sessionId}` as any)}>
          <Text style={s.nextBtnText}>Break the Loop</Text>
          <Ionicons name="sync" size={16} color="#FFF" />
        </TouchableOpacity>
      </View>
      {/* Secondary CTA: Effective Outlets Advisor — for users who'd rather
          process the surfaced emotion via outlets than chain into Loop. */}
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
        <LinearGradient colors={['#EF4444', '#DC2626']} style={s.header}>
          <View style={s.headerTop}>
            <TouchableOpacity style={s.backBtn} onPress={goBack}>
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <AiCreditsBadge compact autoRefresh lowThreshold={trapEst ?? undefined} />
          </View>
          <Text style={s.headerTitle}>Breaking the Trap</Text>
          <Text style={s.headerSub}>{steps[step].title}</Text>
        </LinearGradient>
        {renderProgress()}
        <ScrollView ref={scrollRef} showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
          <VentToOutletsBanner returnTo={(params as any).return_to} returnId={(params as any).return_id} />
          {step === 0 && renderStep0()}
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
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
  progressRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, paddingHorizontal: 20 },
  progressItem: { flexDirection: 'row', alignItems: 'center' },
  progressDot: { width: 26, height: 26, borderRadius: 13, backgroundColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  progressDotActive: { backgroundColor: '#EF4444' },
  progressDotText: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted },
  progressLine: { width: 24, height: 2, backgroundColor: COLORS.border, marginHorizontal: 2 },
  progressLineActive: { backgroundColor: '#EF4444' },
  stepContent: { padding: 16 },
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  stepHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 16, lineHeight: 18 },
  label: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 14, marginBottom: 8 },
  input: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  textArea: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, minHeight: 80, textAlignVertical: 'top', flex: 1 },
  inputRow: { gap: 8 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border },
  chipActive: { backgroundColor: '#EF4444', borderColor: '#EF4444' },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  chipTextActive: { color: '#FFF' },
  boolRow: { flexDirection: 'row', gap: 10 },
  boolBtn: { flex: 1, paddingVertical: 12, borderRadius: 12, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  boolBtnActive: { backgroundColor: '#EF4444', borderColor: '#EF4444' },
  boolText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  boolTextActive: { color: '#FFF' },
  sliderRow: { flexDirection: 'row', gap: 6, justifyContent: 'space-between' },
  sliderDot: { width: 30, height: 30, borderRadius: 15, backgroundColor: '#F3F4F6', justifyContent: 'center', alignItems: 'center' },
  sliderNum: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#EF4444', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
  altBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#FFFFFF', borderColor: '#0EA5E9', borderWidth: 1.5,
    borderRadius: 14, paddingVertical: 12, marginTop: 10,
  },
  altBtnText: { fontSize: 14, fontWeight: '700', color: '#0EA5E9' },
  analysisCard: { borderRadius: 16, padding: 20, marginBottom: 8 },
  analysisTitle: { fontSize: 20, fontWeight: '800', color: '#92400E', marginBottom: 12 },
  analysisBadge: { backgroundColor: '#D97706', alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, marginBottom: 16 },
  analysisBadgeText: { fontSize: 12, fontWeight: '700', color: '#FFF' },
  analysisLabel: { fontSize: 12, fontWeight: '700', color: '#92400E', marginTop: 10, textTransform: 'uppercase' },
  analysisText: { fontSize: 14, color: '#78350F', marginTop: 2, lineHeight: 20 },
  awarenessBox: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginTop: 16 },
  awarenessText: { fontSize: 14, color: '#92400E', flex: 1, lineHeight: 20, fontWeight: '500' },
  interventionBox: { backgroundColor: '#ECFDF5', borderRadius: 12, padding: 14, marginTop: 12 },
  interventionTitle: { fontSize: 14, fontWeight: '700', color: '#065F46' },
  interventionText: { fontSize: 13, color: '#047857', marginTop: 4, lineHeight: 18 },
  actionBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#D1FAE5', borderRadius: 8, padding: 10, marginTop: 10 },
  actionBoxText: { fontSize: 13, fontWeight: '600', color: '#065F46', flex: 1 },
});
