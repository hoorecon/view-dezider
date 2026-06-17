/**
 * /tools/tenses-feels — EG sub-module.
 *
 * Guided coaching flow through the 12-emotion 'Tenses & Feels' framework.
 * For each emotion, the user:
 *   1. Reads the framework definition
 *   2. Sits with the feeling (30s timer)
 *   3. Captures their specific situation + intensity 1–10
 *   4. Receives AI-personalized guidance + the power statement
 *   5. Records a life lesson + constructive action (CCCC)
 *
 * Bottom CTA → Goals & Feels.
 * Top-left arrow → Back to EG hub.
 */
import React, { useState, useMemo, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import {
  ALL_EMOTIONS,
  PAST_EMOTIONS, FUTURE_EMOTIONS,
  PRESENT_SELF_EMOTIONAL, PRESENT_SELF_MENTAL,
  PRESENT_OTHERS_YOURS, PRESENT_OTHERS_THEIRS,
  HEALING_FEELINGS, TENSES_FEELS_INTRO,
  EmotionDef,
} from '../../src/data/tensesFeelsContent';

export default function TensesFeelsScreen() {
  const router = useRouter();
  const [stage, setStage] = useState<'intro' | 'overview' | 'emotion' | 'complete'>('intro');
  const [activeEmotion, setActiveEmotion] = useState<EmotionDef | null>(null);
  const [situation, setSituation] = useState('');
  const [intensity, setIntensity] = useState(5);
  const [lifeLesson, setLifeLesson] = useState('');
  const [constructiveAction, setConstructiveAction] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [aiGuidance, setAiGuidance] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [completedCodes, setCompletedCodes] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/tenses-feels/summary');
        const s = new Set<string>((data?.summary || []).map((r: any) => r.emotion_code));
        setCompletedCodes(s);
      } catch {}
    })();
  }, []);

  const openEmotion = (e: EmotionDef) => {
    setActiveEmotion(e);
    setSituation(''); setIntensity(5); setLifeLesson(''); setConstructiveAction(''); setAiGuidance(null);
    setStage('emotion');
  };

  const runAI = async () => {
    if (!activeEmotion || !situation.trim()) { showAlert('Tell me first', 'Please describe your situation in a few words.'); return; }
    setAiBusy(true);
    try {
      const { data } = await api.post('/tenses-feels/ai-guidance', {
        emotion_code: activeEmotion.code,
        user_situation: situation.trim(),
        intensity,
      });
      setAiGuidance(data);
      if (data?.constructive_action && !constructiveAction) setConstructiveAction(data.constructive_action);
    } catch (e: any) {
      showAlert('AI guidance failed', e?.response?.data?.detail || e.message);
    } finally { setAiBusy(false); }
  };

  const save = async () => {
    if (!activeEmotion) return;
    if (!situation.trim()) { showAlert('Situation required', 'Please describe your situation.'); return; }
    setSaving(true);
    try {
      await api.post('/tenses-feels/reflect', {
        emotion_code: activeEmotion.code,
        user_situation: situation.trim(),
        intensity,
        life_lesson: lifeLesson.trim(),
        constructive_action: constructiveAction.trim(),
        healing_feeling: activeEmotion.healing_feeling,
      });
      setCompletedCodes(prev => new Set([...prev, activeEmotion.code]));
      setStage('overview');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally { setSaving(false); }
  };

  const goBackToEG = () => router.replace('/tools/emotional-gatekeeper' as any);

  // ─── RENDER ───────────────────────────────────────────────────────
  const renderEmotionCard = (e: EmotionDef) => {
    const done = completedCodes.has(e.code);
    return (
      <TouchableOpacity key={e.code} style={[s.emotionCard, done && s.emotionCardDone]} onPress={() => openEmotion(e)} accessibilityLabel={`Open ${e.label} reflection`}>
        <View style={[s.emotionPip, { backgroundColor: e.color }]} />
        <View style={{ flex: 1 }}>
          <Text style={s.emotionLabel}>{e.label}</Text>
          <Text style={s.emotionShort}>{e.short}</Text>
        </View>
        {done && <Ionicons name="checkmark-circle" size={18} color="#10B981" />}
        <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
      </TouchableOpacity>
    );
  };

  const Section = ({ title, hint, items }: { title: string; hint?: string; items: EmotionDef[] }) => (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{title}</Text>
      {!!hint && <Text style={s.sectionHint}>{hint}</Text>}
      {items.map(renderEmotionCard)}
    </View>
  );

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#D97706']} style={s.header}>
        <TouchableOpacity onPress={goBackToEG} style={s.backBtn} accessibilityLabel="Back to Emotional Gatekeeper">
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={s.title}>Tenses & Feels</Text>
        <Text style={s.subtitle}>The 12-emotion framework · Past · Present · Future</Text>
        <View style={s.progressPill}>
          <Ionicons name="sparkles" size={12} color="#FFF" />
          <Text style={s.progressText}>{completedCodes.size} / 12 reflected</Text>
        </View>
      </LinearGradient>

      {stage === 'intro' && (
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Text style={s.introH}>Welcome</Text>
          <Text style={s.introBody}>{TENSES_FEELS_INTRO.welcome}</Text>
          <Text style={s.introBody}>{TENSES_FEELS_INTRO.definition}</Text>
          <View style={s.divider} />
          <Text style={s.introH}>What we'll do</Text>
          <Text style={s.introBody}>{TENSES_FEELS_INTRO.pain_definition}</Text>
          <Text style={s.introBody}>{TENSES_FEELS_INTRO.pain_breakdown}</Text>
          <Text style={s.introHint}>Estimated time: {TENSES_FEELS_INTRO.estimated_minutes} min · you can pause anytime.</Text>
          <TouchableOpacity style={s.primaryBtn} onPress={() => setStage('overview')}>
            <Ionicons name="arrow-forward" size={16} color="#FFF" />
            <Text style={s.primaryBtnText}>  Begin overview</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      {stage === 'overview' && (
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Section title="I. Pain about the PAST" hint="Negative = Clinging · Positive = Longing" items={PAST_EMOTIONS} />
          <Section title="II. Pain about the FUTURE" hint="Negative = Fear · Positive = Anxiety" items={FUTURE_EMOTIONS} />
          <Section title="III-a. PRESENT · Self · Emotional" items={PRESENT_SELF_EMOTIONAL} />
          <Section title="III-b. PRESENT · Self · Mental" items={PRESENT_SELF_MENTAL} />
          <Section title="III-c. PRESENT · Others · Triggers from YOUR side" items={PRESENT_OTHERS_YOURS} />
          <Section title="III-d. PRESENT · Others · Triggers from THEIR side" items={PRESENT_OTHERS_THEIRS} />

          <View style={s.healingCard}>
            <Text style={s.healingHead}>3 Healing Feelings</Text>
            {HEALING_FEELINGS.map(h => (
              <View key={h.code} style={s.healingRow}>
                <Ionicons name={h.icon as any} size={18} color={h.color} />
                <Text style={s.healingLabel}>{h.label}</Text>
              </View>
            ))}
          </View>

          {/* Bottom CTAs */}
          <TouchableOpacity style={[s.primaryBtn, { backgroundColor: '#8B5CF6', marginTop: 14 }]} onPress={() => router.push('/tools/goals-feels' as any)}>
            <Ionicons name="compass" size={16} color="#FFF" />
            <Text style={s.primaryBtnText}>  Continue to Goals & Feels</Text>
          </TouchableOpacity>
          <View style={s.crossNavStrip}>
            <Text style={s.crossNavHead}>Jump to another EG flow:</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
              {[
                { label: 'Reception', href: '/tools/eg-emotional-reception', color: '#0EA5E9' },
                { label: 'Trap', href: '/tools/eg-trap', color: '#EF4444' },
                { label: 'Loop', href: '/tools/eg-loop', color: '#8B5CF6' },
                { label: 'Limitations', href: '/tools/eg-limitation', color: '#3B82F6' },
                { label: 'Effective Outlets', href: '/tools/eg-advisor', color: '#10B981' },
              ].map(x => (
                <TouchableOpacity key={x.label} style={[s.crossNavChip, { borderColor: x.color }]} onPress={() => router.push(x.href as any)}>
                  <Text style={[s.crossNavText, { color: x.color }]}>{x.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </ScrollView>
      )}

      {stage === 'emotion' && activeEmotion && (
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <TouchableOpacity style={s.backLink} onPress={() => setStage('overview')}>
            <Ionicons name="chevron-back" size={14} color="#475569" />
            <Text style={s.backLinkText}>Back to 12 emotions</Text>
          </TouchableOpacity>
          <View style={[s.emotionHeader, { backgroundColor: activeEmotion.color }]}>
            <Text style={s.emotionH}>{activeEmotion.label}</Text>
            <Text style={s.emotionHsub}>{activeEmotion.short}</Text>
          </View>

          <View style={s.coachCard}>
            <Text style={s.coachQuote}>“{activeEmotion.narrative_paraphrase}”</Text>
          </View>

          <View style={s.instructionCard}>
            <Ionicons name="eye-off" size={16} color="#F59E0B" />
            <Text style={s.instructionText}>{activeEmotion.instruction_for_user}</Text>
          </View>

          <Text style={s.lbl}>Describe your specific situation</Text>
          <TextInput style={[s.inp, s.multi]} multiline value={situation} onChangeText={setSituation} placeholder="What's the incident / situation that this emotion attaches to?" placeholderTextColor="#94A3B8" />

          <Text style={s.lbl}>Intensity (1–10)</Text>
          <View style={s.intensityRow}>
            {[1,2,3,4,5,6,7,8,9,10].map(n => (
              <TouchableOpacity key={n} style={[s.iBtn, intensity === n && { backgroundColor: activeEmotion.color, borderColor: activeEmotion.color }]} onPress={() => setIntensity(n)}>
                <Text style={[s.iBtnText, intensity === n && { color: '#FFF' }]}>{n}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <TouchableOpacity style={[s.aiBtn, aiBusy && { opacity: 0.6 }]} onPress={runAI} disabled={aiBusy}>
            {aiBusy ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="sparkles" size={14} color="#FFF" /><Text style={s.aiBtnText}>  Get AI-personalized guidance</Text></>)}
          </TouchableOpacity>

          {aiGuidance && (
            <View style={s.aiResultCard}>
              {aiGuidance.acknowledgement && <View style={s.aiRow}><Text style={s.aiK}>I hear you</Text><Text style={s.aiV}>{aiGuidance.acknowledgement}</Text></View>}
              {aiGuidance.reframe && <View style={s.aiRow}><Text style={s.aiK}>Reframe</Text><Text style={s.aiV}>{aiGuidance.reframe}</Text></View>}
              {aiGuidance.power_statement && <View style={s.aiPowerBox}><Ionicons name="flash" size={12} color="#92400E" /><Text style={s.aiPower}>{aiGuidance.power_statement}</Text></View>}
              {aiGuidance.life_lesson_question && <View style={s.aiRow}><Text style={s.aiK}>Sit with this</Text><Text style={s.aiV}>{aiGuidance.life_lesson_question}</Text></View>}
            </View>
          )}

          <View style={s.principleCard}>
            <Ionicons name="shield-checkmark" size={14} color={activeEmotion.color} />
            <View style={{ flex: 1, marginLeft: 6 }}>
              <Text style={s.principleHead}>Healing principle</Text>
              <Text style={s.principleBody}>{activeEmotion.resolution_quote}</Text>
              <View style={s.powerStatementBox}>
                <Text style={s.powerStatement}>“{activeEmotion.power_statement}”</Text>
              </View>
            </View>
          </View>

          <Text style={s.lbl}>Life lesson</Text>
          <TextInput style={[s.inp, s.multi]} multiline value={lifeLesson} onChangeText={setLifeLesson} placeholder="What can I carry forward so this pattern doesn't repeat?" placeholderTextColor="#94A3B8" />

          <Text style={s.lbl}>One constructive action (CCCC)</Text>
          <TextInput style={s.inp} value={constructiveAction} onChangeText={setConstructiveAction} placeholder="Consistently Constructive with Complete Conviction" placeholderTextColor="#94A3B8" />

          <TouchableOpacity style={[s.primaryBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="save" size={16} color="#FFF" /><Text style={s.primaryBtnText}>  Save reflection</Text></>)}
          </TouchableOpacity>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#FFFBEB' },
  header: { padding: 16, paddingBottom: 20 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 22, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  progressPill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(255,255,255,0.18)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginTop: 8 },
  progressText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  introH: { fontSize: 16, fontWeight: '800', color: '#92400E', marginTop: 8 },
  introBody: { fontSize: 14, color: '#1F2937', lineHeight: 21, marginTop: 6 },
  introHint: { fontSize: 12, color: '#92400E', marginTop: 8, fontStyle: 'italic' },
  divider: { height: 1, backgroundColor: '#FCD34D', marginVertical: 14 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#F59E0B', borderRadius: 12, padding: 14, marginTop: 14 },
  primaryBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  section: { marginBottom: 16 },
  sectionTitle: { fontSize: 13, fontWeight: '800', color: '#92400E', marginBottom: 4 },
  sectionHint: { fontSize: 11, color: '#A16207', marginBottom: 8, fontStyle: 'italic' },
  emotionCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#FCD34D' },
  emotionCardDone: { borderColor: '#10B981', backgroundColor: '#F0FDF4' },
  emotionPip: { width: 8, alignSelf: 'stretch', borderRadius: 4 },
  emotionLabel: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  emotionShort: { fontSize: 11, color: '#64748B', marginTop: 1 },
  healingCard: { backgroundColor: '#FEF3C7', borderRadius: 12, padding: 12, marginTop: 8, borderWidth: 1, borderColor: '#F59E0B' },
  healingHead: { fontSize: 13, fontWeight: '800', color: '#92400E', marginBottom: 8 },
  healingRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  healingLabel: { fontSize: 12, color: '#1F2937', fontWeight: '600' },
  crossNavStrip: { marginTop: 14, padding: 10, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  crossNavHead: { fontSize: 11, color: '#64748B', fontWeight: '700' },
  crossNavChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, borderWidth: 1.5, backgroundColor: '#FFF' },
  crossNavText: { fontSize: 11, fontWeight: '700' },
  backLink: { flexDirection: 'row', alignItems: 'center', gap: 3, marginBottom: 8 },
  backLinkText: { color: '#475569', fontSize: 12, fontWeight: '600' },
  emotionHeader: { padding: 14, borderRadius: 12 },
  emotionH: { color: '#FFF', fontSize: 18, fontWeight: '800' },
  emotionHsub: { color: 'rgba(255,255,255,0.9)', fontSize: 12, marginTop: 2 },
  coachCard: { backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginTop: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  coachQuote: { fontSize: 13, color: '#0F172A', fontStyle: 'italic', lineHeight: 20 },
  instructionCard: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FEF3C7', borderRadius: 10, padding: 10, marginTop: 8 },
  instructionText: { color: '#92400E', fontSize: 12, fontWeight: '600', flex: 1 },
  lbl: { fontSize: 12, fontWeight: '700', color: '#475569', marginTop: 12, marginBottom: 4 },
  inp: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  multi: { minHeight: 70, textAlignVertical: 'top' },
  intensityRow: { flexDirection: 'row', gap: 4, flexWrap: 'wrap' },
  iBtn: { width: 30, height: 32, borderRadius: 6, borderWidth: 1, borderColor: '#CBD5E1', alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF' },
  iBtnText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  aiBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#8B5CF6', borderRadius: 10, padding: 12, marginTop: 12 },
  aiBtnText: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  aiResultCard: { backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12, marginTop: 8, borderWidth: 1, borderColor: '#C4B5FD' },
  aiRow: { paddingVertical: 5 },
  aiK: { fontSize: 10, fontWeight: '800', color: '#7C3AED', textTransform: 'uppercase' },
  aiV: { fontSize: 12, color: '#1F2937', lineHeight: 18, marginTop: 2 },
  aiPowerBox: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FEF3C7', padding: 8, borderRadius: 8, marginTop: 6 },
  aiPower: { flex: 1, color: '#92400E', fontStyle: 'italic', fontSize: 12, fontWeight: '700' },
  principleCard: { flexDirection: 'row', backgroundColor: '#F0FDF4', borderRadius: 10, padding: 12, marginTop: 12, borderWidth: 1, borderColor: '#86EFAC' },
  principleHead: { fontSize: 11, fontWeight: '800', color: '#166534', textTransform: 'uppercase' },
  principleBody: { fontSize: 12, color: '#1F2937', marginTop: 4, lineHeight: 18 },
  powerStatementBox: { backgroundColor: '#FFFFFF', padding: 8, borderRadius: 6, marginTop: 6, borderLeftWidth: 3, borderLeftColor: '#10B981' },
  powerStatement: { fontSize: 12, fontStyle: 'italic', color: '#0F172A', fontWeight: '600' },
});
