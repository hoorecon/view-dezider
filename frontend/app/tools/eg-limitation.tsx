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
import VentToOutletsBanner from '../../src/components/VentToOutletsBanner';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import api from '../../src/utils/api';
import { handleAiError } from '../../src/utils/aiErrors';
import { confirmAiSpend, useAiEstimate } from '../../src/utils/aiEstimates';
import { AiCreditsBadge } from '../../src/components/AiCreditsBadge';
import { Alert } from '../../src/utils/crossAlert';

const LIMITATION_AUDIO_URL = 'https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/qrq3iqkh_Breaking%20the%20LIMITATIONS.mp3';

const LIMITATION_SCRIPT = `Every human being carries invisible limitations — beliefs that silently dictate what they think they can and cannot do. These limitations are not real walls. They are mental constructs built from 4 sources:

1. Past Experience of Self — "I failed before, so I'll fail again." But you are NOT the same person you were then. You've grown, learned, and evolved. Past failure does not equal future failure.

2. Past Experience of Others — "It didn't work for them, so it won't work for me." But YOUR situation is fundamentally different. Different skills, different timing, different resources. Their story is not yours.

3. External Inputs — Social media, news, advertisements, opinions. Information designed to influence you, not inform you. Ask: Is this source authentic? What is the intention behind this information?

4. Fear of the Unknown — "I don't know how, so I can't." But unknown does NOT mean difficult. And even difficult does NOT mean impossible. Everything you know today was once unknown to you.

Identify which source created YOUR limitation. Challenge the hidden assumption. Replace the old belief with an empowering one. You are far more capable than your limitations suggest.`;

const CATEGORIES = [
  { id: 'past_self', name: 'Past Experience of Self', icon: 'person', color: '#EF4444',
    desc: 'Old failures define present capability',
    questions: ['What exactly happened in the past?', 'How have you grown since then?', 'What new skills or understanding do you have now?'] },
  { id: 'past_others', name: 'Past Experience of Others', icon: 'people', color: '#F59E0B',
    desc: "Others' experiences shape your decisions",
    questions: ['Whose experience influenced you?', 'How is YOUR situation different from theirs?', 'What factors existed in their case but not yours?'] },
  { id: 'external_inputs', name: 'External Inputs', icon: 'globe', color: '#8B5CF6',
    desc: 'Social media, news, ads mislead conclusions',
    questions: ['What external source influenced this belief?', 'Is this source authentic and complete?', 'What is the intention behind this information?'] },
  { id: 'fear_unknown', name: 'Fear of Unknown', icon: 'help-circle', color: '#3B82F6',
    desc: 'Unknown \u2260 difficult \u2260 impossible',
    questions: ['What specifically is unknown to you?', 'Is unknown the same as difficult?', 'Even if difficult, does that mean impossible forever?'] },
];

export default function EGLimitationScreen() {
  const router = useRouter();
  const goBack = () => { if (router.canGoBack?.()) router.back(); else router.replace('/tools/emotional-gatekeeper' as any); };
  const params = useLocalSearchParams<{ sessionId: string; return_to?: string; return_id?: string }>();
  const sessionId = params.sessionId;
  const [step, setStep] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ y: 0, animated: false }); }, [step]);
  const [loading, setLoading] = useState(false);
  const [guideExpanded, setGuideExpanded] = useState(false);

  // Step 0: Capture
  const [limitStatement, setLimitStatement] = useState('');
  const [whyLimited, setWhyLimited] = useState('');
  const [origin, setOrigin] = useState('');
  const [beliefDuration, setBeliefDuration] = useState('');
  const [cost, setCost] = useState('');

  // Step 1: Classification
  const [classification, setClassification] = useState<any>(null);
  const [selectedCat, setSelectedCat] = useState('');

  // Step 2: Flow answers
  const [flowAnswers, setFlowAnswers] = useState<Record<string, string>>({});

  // Step 3: Reframe
  const [reframe, setReframe] = useState<any>(null);

  const limClsEst = useAiEstimate('eg_limitation_classify');
  const limRefEst = useAiEstimate('eg_limitation_reframe');

  // Resume an existing in-progress/completed session: prefill inputs and jump to the right step.
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const { data } = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
        const lim = data?.limitation_reflection;
        if (!lim) return;
        setLimitStatement(lim.limitation_statement || '');
        setWhyLimited(lim.why_limited || '');
        setOrigin(lim.origin || '');
        setBeliefDuration(lim.belief_duration || '');
        setCost(lim.cost_of_limitation || '');
        const cls = lim.ai_classification;
        if (cls) { setClassification(cls); setSelectedCat(lim.limitation_category || cls.category || ''); }
        if (lim.flow_answers) setFlowAnswers(lim.flow_answers);
        const rf = lim.ai_summary;
        if (rf && typeof rf === 'object') { setReframe(rf); setStep(2); }
        else if (cls) { setStep(1); }
      } catch { /* ignore resume errors — start fresh */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleCapture = async () => {
    if (!(await confirmAiSpend('eg_limitation_classify', 'Limitation classification'))) return;
    if (!limitStatement.trim()) { Alert.alert('Required', 'Describe your limitation.'); return; }
    setLoading(true);
    try {
      await api.post(`/emotional-gatekeeper/limitation/${sessionId}/capture`, {
        limitation_statement: limitStatement, why_limited: whyLimited,
        origin, belief_duration: beliefDuration, cost_of_limitation: cost,
      });
      const res = await api.post(`/emotional-gatekeeper/limitation/${sessionId}/classify`);
      setClassification(res.data.classification);
      if (res.data.classification?.category) {
        setSelectedCat(res.data.classification.category);
      }
      setStep(1);
    } catch (err) { await handleAiError(err, { router, retry: handleCapture }); }
    finally { setLoading(false); }
  };

  const handleFlow = async () => {
    if (!(await confirmAiSpend('eg_limitation_reframe', 'Limitation reframe'))) return;
    setLoading(true);
    try {
      await api.put(`/emotional-gatekeeper/limitation/${sessionId}/flow`, {
        answers: { ...flowAnswers, selected_category: selectedCat },
      });
      const res = await api.post(`/emotional-gatekeeper/limitation/${sessionId}/reframe`);
      setReframe(res.data.reframe);
      setStep(2);
    } catch (err) { await handleAiError(err, { router, retry: handleFlow }); }
    finally { setLoading(false); }
  };

  const catObj = CATEGORIES.find(c => c.id === selectedCat);

  const renderAudioGuide = () => (
    <View style={s.audioGuideContainer}>
      <TouchableOpacity
        style={s.audioGuideHeader}
        onPress={() => setGuideExpanded(!guideExpanded)}
        activeOpacity={0.7}
      >
        <View style={s.audioGuideIcon}>
          <Ionicons name="headset" size={20} color="#1D4ED8" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.audioGuideTitle}>Audio Guide: Breaking Limitations</Text>
          <Text style={s.audioGuideSub}>Listen to the guided briefing before you begin</Text>
        </View>
        <Ionicons name={guideExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#1D4ED8" />
      </TouchableOpacity>
      {guideExpanded && (
        <View style={s.audioGuideBody}>
          <AudioGuidePlayer
            uri={LIMITATION_AUDIO_URL}
            title="Breaking the LIMITATIONS — Guided Audio"
            color="#3B82F6"
          />
          <View style={s.scriptBox}>
            <View style={s.scriptHeader}>
              <Ionicons name="document-text" size={16} color="#1D4ED8" />
              <Text style={s.scriptLabel}>Briefing Script</Text>
            </View>
            <Text style={s.scriptText}>{LIMITATION_SCRIPT}</Text>
          </View>
        </View>
      )}
    </View>
  );

  const renderStep0 = () => (
    <View style={s.stepContent}>
      {renderAudioGuide()}
      <Text style={s.stepTitle}>What belief is limiting you?</Text>
      <Text style={s.stepHint}>Name the limitation honestly. Awareness is the first step.</Text>
      <View style={s.inputRow}>
        <TextInput style={s.textArea} multiline placeholder="I believe I can't / I'm not able to..."
          value={limitStatement} onChangeText={setLimitStatement} placeholderTextColor={COLORS.textMuted} />
        <VoiceInput sessionId={sessionId || ''} field="limitation" color="#3B82F6"
          onTranscribed={(t) => setLimitStatement(prev => prev ? prev + ' ' + t : t)} />
      </View>
      <Text style={s.label}>Why do you feel limited?</Text>
      <TextInput style={s.textArea} multiline placeholder="Because..."
        value={whyLimited} onChangeText={setWhyLimited} placeholderTextColor={COLORS.textMuted} />
      <Text style={s.label}>Where did this belief originate?</Text>
      <TextInput style={s.input} placeholder="Childhood, failure, someone told me..."
        value={origin} onChangeText={setOrigin} placeholderTextColor={COLORS.textMuted} />
      <Text style={s.label}>How long have you held this belief?</Text>
      <TextInput style={s.input} placeholder="e.g., 5 years, since childhood..."
        value={beliefDuration} onChangeText={setBeliefDuration} placeholderTextColor={COLORS.textMuted} />
      <Text style={s.label}>What has this limitation cost you?</Text>
      <TextInput style={s.textArea} multiline placeholder="Missed opportunities, relationships..."
        value={cost} onChangeText={setCost} placeholderTextColor={COLORS.textMuted} />
      <TouchableOpacity style={s.nextBtn} onPress={handleCapture} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Classify My Limitation{limClsEst ? ` · ~${limClsEst} cr` : ''}</Text><Ionicons name="bulb" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep1 = () => (
    <View style={s.stepContent}>
      {classification && (
        <View style={s.classCard}>
          <Ionicons name="analytics" size={20} color="#1D4ED8" />
          <View style={{ flex: 1 }}>
            <Text style={s.classTitle}>
              AI Classification: {CATEGORIES.find(c => c.id === classification.category)?.name}
              {' '}({Math.round((classification.confidence || 0) * 100)}%)
            </Text>
            <Text style={s.classReason}>{classification.reasoning}</Text>
            <Text style={s.classHidden}>Hidden assumption: {classification.hidden_assumption}</Text>
          </View>
        </View>
      )}
      <Text style={s.stepTitle}>Select or confirm the category</Text>
      {CATEGORIES.map(c => (
        <TouchableOpacity key={c.id} style={[s.catCard, selectedCat === c.id && { borderColor: c.color, borderWidth: 2 }]}
          onPress={() => setSelectedCat(c.id)}>
          <View style={[s.catIcon, { backgroundColor: c.color }]}>
            <Ionicons name={c.icon as any} size={22} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.catName}>{c.name}</Text>
            <Text style={s.catDesc}>{c.desc}</Text>
          </View>
          {selectedCat === c.id && <Ionicons name="checkmark-circle" size={22} color={c.color} />}
        </TouchableOpacity>
      ))}
      {selectedCat && catObj && (
        <>
          <Text style={[s.sectionTitle, { marginTop: 20 }]}>Explore Your Limitation</Text>
          {catObj.questions.map((q, i) => (
            <View key={i}>
              <Text style={s.label}>{q}</Text>
              <View style={s.inputRow}>
                <TextInput style={s.textArea} multiline placeholder="Your reflection..."
                  value={flowAnswers[`q${i}`] || ''}
                  onChangeText={(t) => setFlowAnswers(prev => ({ ...prev, [`q${i}`]: t }))}
                  placeholderTextColor={COLORS.textMuted} />
                <VoiceInput sessionId={sessionId || ''} field={`q${i}`} color="#3B82F6"
                  onTranscribed={(t) => setFlowAnswers(prev => ({ ...prev, [`q${i}`]: (prev[`q${i}`] || '') + ' ' + t }))} />
              </View>
            </View>
          ))}
        </>
      )}
      <TouchableOpacity style={s.nextBtn} onPress={handleFlow} disabled={loading || !selectedCat}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Generate Breakthrough{limRefEst ? ` · ~${limRefEst} cr` : ''}</Text><Ionicons name="sparkles" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep2 = () => (
    <View style={s.stepContent}>
      <LinearGradient colors={['#DBEAFE', '#BFDBFE']} style={s.reframeCard}>
        <Text style={s.reframeTitle}>Limitation Breakthrough</Text>
        {reframe && (
          <>
            <Text style={s.rfLabel}>Old Belief</Text>
            <Text style={s.rfOld}>{reframe.old_belief}</Text>
            <Text style={s.rfLabel}>New Empowering Belief</Text>
            <Text style={s.rfNew}>{reframe.new_belief}</Text>
            <Text style={s.rfLabel}>Growth Evidence</Text>
            <Text style={s.rfText}>{reframe.growth_evidence}</Text>
            <View style={s.rfHighlight}>
              <Ionicons name="sparkles" size={18} color="#1D4ED8" />
              <Text style={s.rfHighlightText}>{reframe.reframe_statement}</Text>
            </View>
            <View style={s.actionBox}>
              <Ionicons name="flash" size={16} color="#D97706" />
              <View style={{ flex: 1 }}>
                <Text style={s.actionTitle}>{reframe.suggested_action}</Text>
                <Text style={s.actionTimeline}>Timeline: {reframe.action_timeline}</Text>
              </View>
            </View>
            <View style={s.affirmBox}>
              <Text style={s.affirmText}>"{reframe.affirmation}"</Text>
            </View>
          </>
        )}
      </LinearGradient>
      <TouchableOpacity style={s.doneBtn} onPress={() => router.push('/tools/emotional-gatekeeper' as any)}>
        <Text style={s.doneBtnText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <LinearGradient colors={['#3B82F6', '#1D4ED8']} style={s.header}>
          <View style={s.headerTop}>
            <TouchableOpacity style={s.backBtn} onPress={goBack}>
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <AiCreditsBadge compact autoRefresh lowThreshold={limRefEst ?? undefined} />
          </View>
          <Text style={s.headerTitle}>Breaking Limitations</Text>
          <Text style={s.headerSub}>
            {step === 0 ? 'Identify the Limitation' : step === 1 ? 'Classify & Explore' : 'Your Breakthrough'}
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
  stepHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  label: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 14, marginBottom: 8 },
  input: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  textArea: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, minHeight: 80, textAlignVertical: 'top', flex: 1 },
  inputRow: { gap: 8 },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#3B82F6', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  classCard: { flexDirection: 'row', gap: 10, backgroundColor: '#EFF6FF', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#BFDBFE' },
  classTitle: { fontSize: 14, fontWeight: '700', color: '#1E40AF' },
  classReason: { fontSize: 12, color: '#1E3A8A', marginTop: 4 },
  classHidden: { fontSize: 11, color: '#3730A3', marginTop: 4, fontStyle: 'italic' },
  catCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  catIcon: { width: 44, height: 44, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  catName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  catDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  reframeCard: { borderRadius: 16, padding: 20 },
  reframeTitle: { fontSize: 20, fontWeight: '800', color: '#1E3A8A', marginBottom: 12 },
  rfLabel: { fontSize: 12, fontWeight: '700', color: '#1E40AF', marginTop: 10, textTransform: 'uppercase' },
  rfOld: { fontSize: 14, color: '#991B1B', marginTop: 2, textDecorationLine: 'line-through' },
  rfNew: { fontSize: 15, color: '#065F46', marginTop: 2, fontWeight: '600' },
  rfText: { fontSize: 14, color: '#1E3A8A', marginTop: 2, lineHeight: 20 },
  rfHighlight: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginTop: 16 },
  rfHighlightText: { fontSize: 14, color: '#1E40AF', flex: 1, lineHeight: 20, fontWeight: '500' },
  actionBox: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFFBEB', borderRadius: 10, padding: 12, marginTop: 12 },
  actionTitle: { fontSize: 13, fontWeight: '600', color: '#92400E' },
  actionTimeline: { fontSize: 11, color: '#B45309', marginTop: 2 },
  affirmBox: { backgroundColor: 'rgba(59,130,246,0.1)', borderRadius: 10, padding: 14, marginTop: 12, alignItems: 'center' },
  affirmText: { fontSize: 14, fontWeight: '600', color: '#1D4ED8', fontStyle: 'italic', textAlign: 'center' },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },

  // Audio Guide
  audioGuideContainer: { backgroundColor: '#FFF', borderRadius: 14, marginBottom: 16, borderWidth: 1, borderColor: '#DBEAFE', overflow: 'hidden' },
  audioGuideHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14 },
  audioGuideIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#DBEAFE', justifyContent: 'center', alignItems: 'center' },
  audioGuideTitle: { fontSize: 14, fontWeight: '700', color: '#1E40AF' },
  audioGuideSub: { fontSize: 11, color: '#3B82F6', marginTop: 2 },
  audioGuideBody: { paddingHorizontal: 14, paddingBottom: 14 },
  scriptBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 14, marginTop: 10, borderLeftWidth: 3, borderLeftColor: '#3B82F6' },
  scriptHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  scriptLabel: { fontSize: 12, fontWeight: '700', color: '#1D4ED8', textTransform: 'uppercase' },
  scriptText: { fontSize: 13, color: '#475569', lineHeight: 20, fontStyle: 'italic' },
});
