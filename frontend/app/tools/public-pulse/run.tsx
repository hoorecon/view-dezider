import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { showAlert } from '../../../src/utils/alert';
import { safeBack } from '../../../src/utils/navigation';

type Question = {
  id: string;
  type: string;
  label: string;
  options?: string[];
  required?: boolean;
  default?: any;
  min?: number;
  max?: number;
  soft_phrasing?: string;
  sensitive?: boolean;
};

type Step = {
  step: number;
  title: string;
  subtitle?: string;
  questions: Question[];
  show_teaser?: boolean;
  show_partial_result?: boolean;
  is_final?: boolean;
};

const labelize = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function RunToolScreen() {
  const router = useRouter();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [tool, setTool] = useState<any>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [teaser, setTeaser] = useState<any>(null);
  const [partial, setPartial] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        const [toolRes, startRes] = await Promise.all([
          api.get(`/public-pulse/tools/${slug}`),
          api.post(`/public-pulse/tools/${slug}/start`, {}),
        ]);
        setTool(toolRes.data);
        setSessionId(startRes.data.session_id);
      } catch (e: any) {
        showAlert('Error', e?.response?.data?.detail || 'Failed to start tool');
        safeBack(router);
      } finally {
        setLoading(false);
      }
    };
    if (slug) init();
  }, [slug]);

  const currentStep: Step | undefined = tool?.steps?.[stepIndex];
  const totalSteps = tool?.steps?.length || 0;
  const progress = totalSteps ? ((stepIndex + 1) / totalSteps) * 100 : 0;

  const setAnswer = (qid: string, val: any) => setAnswers({ ...answers, [qid]: val });

  const validate = () => {
    if (!currentStep) return false;
    for (const q of currentStep.questions) {
      if (q.required && (answers[q.id] === undefined || answers[q.id] === '' || answers[q.id] === null)) {
        showAlert('Required', `Please answer: ${q.label}`);
        return false;
      }
    }
    return true;
  };

  const submitStep = async () => {
    if (!validate() || !sessionId || !currentStep) return;
    setSubmitting(true);
    try {
      // Only send the questions for the current step
      const stepAnswers: Record<string, any> = {};
      for (const q of currentStep.questions) {
        if (answers[q.id] !== undefined) stepAnswers[q.id] = answers[q.id];
      }
      const res = await api.post(`/public-pulse/tools/sessions/${sessionId}/answer`, {
        step: currentStep.step,
        answers: stepAnswers,
      });
      setTeaser(res.data.teaser || null);
      setPartial(res.data.partial_result || null);

      if (currentStep.is_final) {
        // Move to result screen
        const completion = await api.post(`/public-pulse/tools/sessions/${sessionId}/complete`, {
          contribute_to_research: true,
        });
        router.replace(`/tools/public-pulse/result?session=${sessionId}` as any);
      } else {
        setStepIndex(stepIndex + 1);
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !tool || !currentStep) {
    return <SafeAreaView style={styles.container}><ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} /></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
          {/* Header */}
          <View style={styles.header}>
            <TouchableOpacity onPress={() => safeBack(router)}>
              <Ionicons name="close" size={28} color={COLORS.text} />
            </TouchableOpacity>
            <Text style={styles.headerStep}>Step {currentStep.step} of {totalSteps}</Text>
            <View style={{ width: 28 }} />
          </View>

          {/* Progress bar */}
          <View style={styles.progressBarBg}>
            <View style={[styles.progressBarFill, { width: `${progress}%`, backgroundColor: tool.color }]} />
          </View>

          {/* Tool title */}
          <View style={styles.toolHeader}>
            <Text style={styles.toolTitle}>{tool.title}</Text>
            <Text style={styles.tagline}>{tool.tagline}</Text>
          </View>

          {/* Step title */}
          <View style={{ paddingHorizontal: 20, marginTop: 8 }}>
            <Text style={styles.stepTitle}>{currentStep.title}</Text>
            {currentStep.subtitle && <Text style={styles.stepSubtitle}>{currentStep.subtitle}</Text>}
          </View>

          {/* Questions */}
          <View style={styles.questionsWrap}>
            {currentStep.questions.map((q) => (
              <View key={q.id} style={styles.qBlock}>
                <Text style={styles.qLabel}>
                  {q.label}
                  {!q.required && <Text style={styles.optional}> (optional)</Text>}
                </Text>
                {q.soft_phrasing && (
                  <Text style={styles.softHint}>
                    <Ionicons name="information-circle-outline" size={12} color="#6B7280" /> {q.soft_phrasing}
                  </Text>
                )}
                {q.sensitive && (
                  <View style={styles.sensitiveBadge}>
                    <Ionicons name="lock-closed" size={10} color="#92400E" />
                    <Text style={styles.sensitiveTxt}>Sensitive — never shared individually</Text>
                  </View>
                )}

                {q.type === 'text' && (
                  <TextInput
                    style={styles.textInput}
                    value={answers[q.id] || ''}
                    onChangeText={(v) => setAnswer(q.id, v)}
                    placeholder="Type here..."
                    placeholderTextColor="#9CA3AF"
                  />
                )}
                {q.type === 'number' && (
                  <TextInput
                    style={styles.textInput}
                    value={answers[q.id]?.toString() || ''}
                    onChangeText={(v) => setAnswer(q.id, parseInt(v) || 0)}
                    placeholder="0"
                    placeholderTextColor="#9CA3AF"
                    keyboardType="number-pad"
                  />
                )}
                {q.type === 'single_select' && q.options && (
                  <View style={styles.chipWrap}>
                    {q.options.map((opt) => {
                      const sel = answers[q.id] === opt;
                      return (
                        <TouchableOpacity
                          key={opt}
                          style={[styles.chip, sel && { backgroundColor: tool.color, borderColor: tool.color }]}
                          onPress={() => setAnswer(q.id, opt)}
                        >
                          <Text style={[styles.chipTxt, sel && { color: '#FFF' }]}>{labelize(opt)}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
                {q.type === 'boolean' && (
                  <View style={styles.boolRow}>
                    {[
                      { v: true, lbl: 'Yes' },
                      { v: false, lbl: 'No' },
                    ].map((b) => {
                      const sel = answers[q.id] === b.v;
                      return (
                        <TouchableOpacity
                          key={b.lbl}
                          style={[styles.boolBtn, sel && { backgroundColor: tool.color, borderColor: tool.color }]}
                          onPress={() => setAnswer(q.id, b.v)}
                        >
                          <Text style={[styles.boolTxt, sel && { color: '#FFF' }]}>{b.lbl}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
                {q.type === 'slider' && q.min !== undefined && q.max !== undefined && (
                  <View style={styles.sliderRow}>
                    {Array.from({ length: q.max - q.min + 1 }, (_, i) => i + (q.min || 0)).map((n) => {
                      const sel = answers[q.id] === n;
                      return (
                        <TouchableOpacity
                          key={n}
                          style={[styles.sliderDot, sel && { backgroundColor: tool.color, borderColor: tool.color }]}
                          onPress={() => setAnswer(q.id, n)}
                        >
                          <Text style={[styles.sliderTxt, sel && { color: '#FFF' }]}>{n}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
              </View>
            ))}
          </View>

          {/* Teaser from previous step */}
          {teaser && (
            <View style={styles.teaserCard}>
              <Ionicons name="trending-up" size={18} color="#10B981" />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.teaserText}>{teaser.lead}</Text>
                {teaser.synthetic && <Text style={styles.teaserSynth}>Estimate — will become precise as more people contribute</Text>}
              </View>
            </View>
          )}

          {/* Partial result */}
          {partial && partial.label && (
            <View style={[styles.partialCard, { backgroundColor: `${partial.color}15`, borderColor: partial.color }]}>
              <Text style={[styles.partialLabel, { color: partial.color }]}>{partial.label}</Text>
              <Text style={styles.partialHint}>{partial.hint}</Text>
            </View>
          )}
        </ScrollView>

        {/* Submit */}
        <View style={styles.footer}>
          <TouchableOpacity
            style={[styles.nextBtn, { backgroundColor: tool.color }]}
            onPress={submitStep}
            disabled={submitting}
          >
            {submitting ? <ActivityIndicator color="#FFF" /> : (
              <Text style={styles.nextBtnTxt}>
                {currentStep.is_final ? 'Get my Score™' : `Next →`}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerStep: { fontSize: 13, fontWeight: '600', color: '#6B7280' },
  progressBarBg: { height: 4, backgroundColor: '#E5E7EB', marginHorizontal: 16, borderRadius: 2, overflow: 'hidden' },
  progressBarFill: { height: '100%' },
  toolHeader: { paddingHorizontal: 20, marginTop: 16 },
  toolTitle: { fontSize: 22, fontWeight: '800', color: COLORS.text },
  tagline: { fontSize: 12, color: '#6B7280', marginTop: 4, fontWeight: '600' },
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginTop: 16 },
  stepSubtitle: { fontSize: 13, color: '#6B7280', marginTop: 4 },
  questionsWrap: { paddingHorizontal: 20, marginTop: 16 },
  qBlock: { marginBottom: 24 },
  qLabel: { fontSize: 14, fontWeight: '600', color: COLORS.text, marginBottom: 8 },
  optional: { color: '#9CA3AF', fontWeight: '500' },
  softHint: { fontSize: 11, color: '#6B7280', marginBottom: 8, lineHeight: 16 },
  sensitiveBadge: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FEF3C7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start', marginBottom: 8, gap: 4 },
  sensitiveTxt: { fontSize: 10, color: '#92400E', fontWeight: '600' },
  textInput: {
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB',
    borderRadius: 10, padding: 12, fontSize: 15, color: COLORS.text,
  },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: 20,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB',
  },
  chipTxt: { fontSize: 13, color: COLORS.text, fontWeight: '500' },
  boolRow: { flexDirection: 'row', gap: 12 },
  boolBtn: { flex: 1, paddingVertical: 14, borderRadius: 10, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB', alignItems: 'center' },
  boolTxt: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  sliderRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  sliderDot: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB', alignItems: 'center', justifyContent: 'center' },
  sliderTxt: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  teaserCard: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#ECFDF5', borderRadius: 12,
    padding: 14, marginHorizontal: 20, marginVertical: 12,
    borderWidth: 1, borderColor: '#A7F3D0',
  },
  teaserText: { fontSize: 13, color: '#065F46', fontWeight: '600', lineHeight: 18 },
  teaserSynth: { fontSize: 10, color: '#065F46', marginTop: 4, fontStyle: 'italic' },
  partialCard: { padding: 14, marginHorizontal: 20, marginVertical: 8, borderRadius: 10, borderWidth: 1 },
  partialLabel: { fontSize: 14, fontWeight: '700' },
  partialHint: { fontSize: 12, color: '#374151', marginTop: 4 },
  footer: { padding: 16, backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: '#E5E7EB' },
  nextBtn: { padding: 16, borderRadius: 12, alignItems: 'center' },
  nextBtnTxt: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
