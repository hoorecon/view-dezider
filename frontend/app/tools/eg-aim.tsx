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
import api from '../../src/utils/api';
import { handleAiError } from '../../src/utils/aiErrors';
import { confirmAiSpend, useAiEstimate } from '../../src/utils/aiEstimates';
import { AiCreditsBadge } from '../../src/components/AiCreditsBadge';
import { Alert } from '../../src/utils/crossAlert';

interface Addiction {
  area_of_life: string; addiction: string; triggering_situations: string;
  positive_impact: string; positive_impact_pct: number;
  positive_impact_areas?: string[];
  negative_impact: string; negative_impact_pct: number;
  negative_impact_areas?: string[];
}
interface Irritation {
  area_of_life: string; irritation: string; probable_reaction: string;
  positive_impact: string; negative_impact: string;
  irritation_pct?: number;
  negative_impact_areas?: string[];
}

export default function EGAimScreen() {
  const router = useRouter();
  const goBack = () => { if (router.canGoBack?.()) router.back(); else router.replace('/tools/emotional-gatekeeper' as any); };
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [step, setStep] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ y: 0, animated: false }); }, [step]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [lifeAreas, setLifeAreas] = useState<{id: string; name: string}[]>([]);
  const aimEst = useAiEstimate('eg_aim_analyze');

  const [addictions, setAddictions] = useState<Addiction[]>([]);
  const [irritations, setIrritations] = useState<Irritation[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);

  // Resume an in-progress/completed session: prefill entries and jump to insights if analyzed.
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const { data } = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
        const a = data?.aim_reflection;
        if (!a) return;
        if (Array.isArray(a.addictions)) setAddictions(a.addictions);
        if (Array.isArray(a.irritations)) setIrritations(a.irritations);
        if (a.ai_analysis) { setAnalysis(a.ai_analysis); setStep(1); }
      } catch { /* ignore */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // New addiction form
  const [addArea, setAddArea] = useState('');
  const [addName, setAddName] = useState('');
  const [addTrigger, setAddTrigger] = useState('');
  const [addPosImpact, setAddPosImpact] = useState('');
  const [addPosPct, setAddPosPct] = useState(50);
  const [addPosAreas, setAddPosAreas] = useState<string[]>([]);
  const [addNegImpact, setAddNegImpact] = useState('');
  const [addNegPct, setAddNegPct] = useState(50);
  const [addNegAreas, setAddNegAreas] = useState<string[]>([]);

  // New irritation form. `irrPct` is MANDATORY (pre-filled at 50% so the
  // user has a working baseline). `irrNegAreas` is the multi-select of
  // life areas this irritation harms.
  const [irrArea, setIrrArea] = useState('');
  const [irrName, setIrrName] = useState('');
  const [irrPct, setIrrPct] = useState(50);
  const [irrReaction, setIrrReaction] = useState('');
  const [irrPosImpact, setIrrPosImpact] = useState('');
  const [irrNegImpact, setIrrNegImpact] = useState('');
  const [irrNegAreas, setIrrNegAreas] = useState<string[]>([]);

  // Toggle helper for multi-select chips.
  const toggleIn = (arr: string[], id: string) =>
    arr.includes(id) ? arr.filter(x => x !== id) : [...arr, id];

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/emotional-gatekeeper/aim/options');
        setLifeAreas(res.data.life_areas || []);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    })();
  }, []);

  const addAddiction = () => {
    if (!addName.trim()) { Alert.alert('Required', 'Name the addiction.'); return; }
    setAddictions(prev => [...prev, {
      area_of_life: addArea || 'other', addiction: addName, triggering_situations: addTrigger,
      positive_impact: addPosImpact, positive_impact_pct: addPosPct, positive_impact_areas: addPosAreas,
      negative_impact: addNegImpact, negative_impact_pct: addNegPct, negative_impact_areas: addNegAreas,
    }]);
    setAddName(''); setAddTrigger(''); setAddPosImpact(''); setAddNegImpact('');
    setAddPosPct(50); setAddNegPct(50); setAddArea('');
    setAddPosAreas([]); setAddNegAreas([]);
  };

  const addIrritation = () => {
    if (!irrName.trim()) { Alert.alert('Required', 'Name the irritation.'); return; }
    setIrritations(prev => [...prev, {
      area_of_life: irrArea || 'other', irritation: irrName, irritation_pct: irrPct,
      probable_reaction: irrReaction, positive_impact: irrPosImpact, negative_impact: irrNegImpact,
      negative_impact_areas: irrNegAreas,
    }]);
    setIrrName(''); setIrrReaction(''); setIrrPosImpact(''); setIrrNegImpact('');
    setIrrArea(''); setIrrPct(50); setIrrNegAreas([]);
  };

  const handleSaveAndAnalyze = async () => {
    if (addictions.length === 0 && irritations.length === 0) {
      Alert.alert('Required', 'Add at least one addiction or irritation.'); return;
    }
    if (!(await confirmAiSpend('eg_aim_analyze', 'Aim analysis'))) return;
    setSubmitting(true);
    try {
      await api.post(`/emotional-gatekeeper/aim/${sessionId}/save`, { addictions, irritations });
      const res = await api.post(`/emotional-gatekeeper/aim/${sessionId}/analyze`);
      setAnalysis(res.data.analysis);
      setStep(1);
    } catch (err) { await handleAiError(err, { router, retry: handleSaveAndAnalyze }); }
    finally { setSubmitting(false); }
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#F97316" />
        </View>
      </SafeAreaView>
    );
  }

  const renderStep0 = () => (
    <View style={s.stepContent}>
      {/* ADDICTIONS SECTION */}
      <Text style={s.stepTitle}>Your Addictions</Text>
      <Text style={s.stepHint}>Behaviors you feel drawn to repeatedly, even when they may not serve you.</Text>
      {addictions.map((a, i) => (
        <View key={i} style={s.entryCard}>
          <View style={s.entryHeader}>
            <Ionicons name="flame" size={16} color="#F97316" />
            <Text style={s.entryTitle}>{a.addiction}</Text>
            <TouchableOpacity onPress={() => setAddictions(prev => prev.filter((_, j) => j !== i))}>
              <Ionicons name="close-circle" size={20} color="#EF4444" />
            </TouchableOpacity>
          </View>
          <Text style={s.entryMeta}>{a.area_of_life} • +{a.positive_impact_pct}% / -{a.negative_impact_pct}%</Text>
        </View>
      ))}
      <View style={s.formCard}>
        <Text style={s.formLabel}>Life Area</Text>
        {/* Wrap to multiple rows so users see all life-area pills at a
            glance — horizontal scroll hid pills off-screen. */}
        <View style={[s.chipRow, { marginBottom: 8 }]}>
          {lifeAreas.map(la => (
            <TouchableOpacity key={la.id} style={[s.chip, addArea === la.id && s.chipActive]}
              onPress={() => setAddArea(la.id)}>
              <Text style={[s.chipText, addArea === la.id && s.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={s.formLabel}>Addiction / Behavior</Text>
        <View style={s.inputRow}>
          <TextInput style={s.input} placeholder="e.g., Scrolling social media, Overeating..."
            value={addName} onChangeText={setAddName} placeholderTextColor={COLORS.textMuted} />
          <VoiceInput sessionId={sessionId || ''} field="addiction" color="#F97316"
            onTranscribed={(t) => setAddName(prev => prev ? prev + ' ' + t : t)} />
        </View>
        <Text style={s.formLabel}>Triggering Situations</Text>
        <TextInput style={s.input} placeholder="When bored, after conflict..."
          value={addTrigger} onChangeText={setAddTrigger} placeholderTextColor={COLORS.textMuted} />
        <View style={s.impactRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.formLabel}>Positive Impact (%)</Text>
            <View style={s.pctRow}>
              <TouchableOpacity onPress={() => setAddPosPct(Math.max(0, addPosPct - 10))}>
                <Ionicons name="remove-circle" size={24} color="#10B981" />
              </TouchableOpacity>
              <Text style={s.pctNum}>{addPosPct}%</Text>
              <TouchableOpacity onPress={() => setAddPosPct(Math.min(100, addPosPct + 10))}>
                <Ionicons name="add-circle" size={24} color="#10B981" />
              </TouchableOpacity>
            </View>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.formLabel}>Negative Impact (%)</Text>
            <View style={s.pctRow}>
              <TouchableOpacity onPress={() => setAddNegPct(Math.max(0, addNegPct - 10))}>
                <Ionicons name="remove-circle" size={24} color="#EF4444" />
              </TouchableOpacity>
              <Text style={s.pctNum}>{addNegPct}%</Text>
              <TouchableOpacity onPress={() => setAddNegPct(Math.min(100, addNegPct + 10))}>
                <Ionicons name="add-circle" size={24} color="#EF4444" />
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Item 3 — describe the positive impact in free text + mark which
            life areas benefit (multi-select). All optional. */}
        <Text style={s.formLabel}>What kind of positive impact? (optional)</Text>
        <TextInput style={s.input} placeholder="e.g., stress relief, social connection..."
          value={addPosImpact} onChangeText={setAddPosImpact} placeholderTextColor={COLORS.textMuted} />
        <Text style={s.formLabel}>Positively affected life areas (optional)</Text>
        <View style={[s.chipRow, { marginBottom: 8 }]}>
          {lifeAreas.map(la => (
            <TouchableOpacity key={`pa-${la.id}`} style={[s.chip, addPosAreas.includes(la.id) && s.chipActive]}
              onPress={() => setAddPosAreas(prev => toggleIn(prev, la.id))}>
              <Text style={[s.chipText, addPosAreas.includes(la.id) && s.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={s.formLabel}>What kind of negative impact? (optional)</Text>
        <TextInput style={s.input} placeholder="e.g., lost productivity, weight gain..."
          value={addNegImpact} onChangeText={setAddNegImpact} placeholderTextColor={COLORS.textMuted} />
        <Text style={s.formLabel}>Negatively affected life areas (optional)</Text>
        <View style={[s.chipRow, { marginBottom: 8 }]}>
          {lifeAreas.map(la => (
            <TouchableOpacity key={`na-${la.id}`} style={[s.chip, addNegAreas.includes(la.id) && s.chipActive]}
              onPress={() => setAddNegAreas(prev => toggleIn(prev, la.id))}>
              <Text style={[s.chipText, addNegAreas.includes(la.id) && s.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={s.addBtn} onPress={addAddiction}>
          <Ionicons name="add" size={18} color="#F97316" />
          <Text style={s.addBtnText}>Add Addiction</Text>
        </TouchableOpacity>
      </View>

      {/* IRRITATIONS SECTION */}
      <Text style={[s.stepTitle, { marginTop: 24 }]}>Your Irritations</Text>
      <Text style={s.stepHint}>Situations or behaviors of others that trigger strong reactions in you.</Text>
      {irritations.map((ir, i) => (
        <View key={i} style={s.entryCard}>
          <View style={s.entryHeader}>
            <Ionicons name="thunderstorm" size={16} color="#EF4444" />
            <Text style={s.entryTitle}>{ir.irritation}</Text>
            <TouchableOpacity onPress={() => setIrritations(prev => prev.filter((_, j) => j !== i))}>
              <Ionicons name="close-circle" size={20} color="#EF4444" />
            </TouchableOpacity>
          </View>
          <Text style={s.entryMeta}>{ir.area_of_life} • Reaction: {ir.probable_reaction || 'Not specified'}</Text>
        </View>
      ))}
      <View style={s.formCard}>
        <Text style={s.formLabel}>Life Area</Text>
        {/* Wrap to multiple rows — see comment above. */}
        <View style={[s.chipRow, { marginBottom: 8 }]}>
          {lifeAreas.map(la => (
            <TouchableOpacity key={la.id} style={[s.chip, irrArea === la.id && s.chipActive]}
              onPress={() => setIrrArea(la.id)}>
              <Text style={[s.chipText, irrArea === la.id && s.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={s.formLabel}>Irritation</Text>
        <View style={s.inputRow}>
          <TextInput style={s.input} placeholder="e.g., Being interrupted, Traffic..."
            value={irrName} onChangeText={setIrrName} placeholderTextColor={COLORS.textMuted} />
          <VoiceInput sessionId={sessionId || ''} field="irritation" color="#F97316"
            onTranscribed={(t) => setIrrName(prev => prev ? prev + ' ' + t : t)} />
        </View>
        <Text style={s.formLabel}>Your Probable Reaction</Text>
        <TextInput style={s.input} placeholder="I usually react by..."
          value={irrReaction} onChangeText={setIrrReaction} placeholderTextColor={COLORS.textMuted} />

        {/* Item 3 — Irritation % (mandatory, defaults 50%) + negatively-affected
            life areas (multi-select, optional). */}
        <Text style={s.formLabel}>Irritation strength · <Text style={{ color: '#EF4444' }}>required</Text></Text>
        <View style={s.pctRow}>
          <TouchableOpacity onPress={() => setIrrPct(Math.max(0, irrPct - 10))}>
            <Ionicons name="remove-circle" size={24} color="#EF4444" />
          </TouchableOpacity>
          <Text style={s.pctNum}>{irrPct}%</Text>
          <TouchableOpacity onPress={() => setIrrPct(Math.min(100, irrPct + 10))}>
            <Ionicons name="add-circle" size={24} color="#EF4444" />
          </TouchableOpacity>
        </View>
        <Text style={s.formLabel}>Negatively affected life areas (optional)</Text>
        <View style={[s.chipRow, { marginBottom: 8 }]}>
          {lifeAreas.map(la => (
            <TouchableOpacity key={`irrn-${la.id}`} style={[s.chip, irrNegAreas.includes(la.id) && s.chipActive]}
              onPress={() => setIrrNegAreas(prev => toggleIn(prev, la.id))}>
              <Text style={[s.chipText, irrNegAreas.includes(la.id) && s.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={s.addBtn} onPress={addIrritation}>
          <Ionicons name="add" size={18} color="#F97316" />
          <Text style={s.addBtnText}>Add Irritation</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={s.nextBtn} onPress={handleSaveAndAnalyze} disabled={submitting}>
        {submitting ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Analyze & Get Insights{aimEst ? ` · ~${aimEst} cr` : ''}</Text><Ionicons name="analytics" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderStep1 = () => (
    <View style={s.stepContent}>
      <LinearGradient colors={['#FFF7ED', '#FFEDD5']} style={s.resultCard}>
        <Text style={s.resultTitle}>AIM Analysis</Text>
        {analysis?.self_awareness_summary && (
          <View style={s.summaryBox}>
            <Ionicons name="bulb" size={18} color="#EA580C" />
            <Text style={s.summaryText}>{analysis.self_awareness_summary}</Text>
          </View>
        )}
        {analysis?.addictions_analysis?.map((a: any, i: number) => (
          <View key={i} style={s.analysisItem}>
            <View style={s.analysisHeader}>
              <Ionicons name="flame" size={16} color="#F97316" />
              <Text style={s.analysisName}>{a.addiction}</Text>
              <View style={[s.sevBadge, { backgroundColor: a.severity === 'high' ? '#EF4444' : a.severity === 'medium' ? '#F59E0B' : '#10B981' }]}>
                <Text style={s.sevText}>{a.severity}</Text>
              </View>
            </View>
            <Text style={s.analysisDetail}>Root: {a.root_pattern}</Text>
            <Text style={s.analysisDetail}>Action: {a.corrective_action}</Text>
            <Text style={s.analysisDetail}>Replace with: {a.replacement_behavior}</Text>
            <Text style={s.analysisMeta}>Timeline: {a.timeline}</Text>
          </View>
        ))}
        {analysis?.irritations_analysis?.map((ir: any, i: number) => (
          <View key={i} style={s.analysisItem}>
            <View style={s.analysisHeader}>
              <Ionicons name="thunderstorm" size={16} color="#EF4444" />
              <Text style={s.analysisName}>{ir.irritation}</Text>
            </View>
            <Text style={s.analysisDetail}>Pattern: {ir.reaction_pattern}</Text>
            <Text style={s.analysisDetail}>Root emotion: {ir.emotional_root}</Text>
            <Text style={s.analysisDetail}>Constructive response: {ir.constructive_response}</Text>
            <Text style={s.analysisMeta}>Practice: {ir.practice_tip}</Text>
          </View>
        ))}
        {analysis?.top_priorities?.map((p: string, i: number) => (
          <View key={i} style={s.prioItem}>
            <Text style={s.prioNum}>{i + 1}</Text>
            <Text style={s.prioText}>{p}</Text>
          </View>
        ))}
      </LinearGradient>
      <TouchableOpacity style={s.doneBtn} onPress={() => router.push('/tools/emotional-gatekeeper' as any)}>
        <Text style={s.doneBtnText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <LinearGradient colors={['#F97316', '#EA580C']} style={s.header}>
          <View style={s.headerTop}>
            <TouchableOpacity style={s.backBtn} onPress={goBack}>
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <AiCreditsBadge compact autoRefresh lowThreshold={aimEst ?? undefined} />
          </View>
          <Text style={s.headerTitle}>AIM Manager</Text>
          <Text style={s.headerSub}>{step === 0 ? 'Log Addictions & Irritations' : 'AI Insights'}</Text>
        </LinearGradient>
        <ScrollView ref={scrollRef} showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
          {step === 0 && renderStep0()}
          {step === 1 && renderStep1()}
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
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  stepHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 12 },
  entryCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  entryHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  entryTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  entryMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, marginLeft: 24 },
  formCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginTop: 8, borderWidth: 1, borderColor: '#FED7AA' },
  formLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 8, marginBottom: 4 },
  input: { backgroundColor: '#F9FAFB', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, flex: 1 },
  inputRow: { gap: 6 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, rowGap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: COLORS.border },
  chipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  chipText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  chipTextActive: { color: '#FFF' },
  impactRow: { flexDirection: 'row', gap: 12, marginTop: 8 },
  pctRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12 },
  pctNum: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, marginTop: 8, borderRadius: 10, borderWidth: 1, borderColor: '#F97316', borderStyle: 'dashed' },
  addBtnText: { fontSize: 13, fontWeight: '600', color: '#F97316' },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#F97316', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  resultCard: { borderRadius: 16, padding: 20 },
  resultTitle: { fontSize: 20, fontWeight: '800', color: '#9A3412', marginBottom: 12 },
  summaryBox: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginBottom: 16 },
  summaryText: { fontSize: 13, color: '#9A3412', flex: 1, lineHeight: 18 },
  analysisItem: { backgroundColor: 'rgba(255,255,255,0.5)', borderRadius: 12, padding: 12, marginBottom: 10 },
  analysisHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  analysisName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  sevBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  sevText: { fontSize: 10, fontWeight: '700', color: '#FFF', textTransform: 'uppercase' },
  analysisDetail: { fontSize: 12, color: '#78350F', lineHeight: 17, marginTop: 2 },
  analysisMeta: { fontSize: 11, color: '#B45309', marginTop: 4, fontStyle: 'italic' },
  prioItem: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', marginTop: 8 },
  prioNum: { fontSize: 14, fontWeight: '800', color: '#EA580C', width: 20 },
  prioText: { fontSize: 13, color: '#9A3412', flex: 1, lineHeight: 18 },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
});
