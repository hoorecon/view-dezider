import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const FREQ_OPTIONS = [
  { id: 'often', label: 'Often (6-7/wk)', color: '#EF4444' },
  { id: 'sometimes', label: 'Sometimes (3-5/wk)', color: '#F59E0B' },
  { id: 'rarely', label: 'Rarely (1-2/wk)', color: '#10B981' },
  { id: 'not_at_all', label: 'Not at all', color: '#6B7280' },
];

const NATURE_COLORS: Record<string, string> = {
  physical: '#EF4444', mental: '#3B82F6', emotional: '#F59E0B', energy: '#8B5CF6',
};

interface Strategy {
  id: string; name: string; nature: string; default_constructive: boolean | null;
}
interface Selection {
  strategy_id: string; frequency: string; is_compulsive: boolean;
}

export default function EGOutletScreen() {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selections, setSelections] = useState<Record<string, Selection>>({});
  const [analysis, setAnalysis] = useState<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/emotional-gatekeeper/outlet/strategies');
        setStrategies(res.data.strategies || []);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    })();
  }, []);

  const toggleStrategy = (id: string) => {
    setSelections(prev => {
      if (prev[id]) { const n = { ...prev }; delete n[id]; return n; }
      return { ...prev, [id]: { strategy_id: id, frequency: 'sometimes', is_compulsive: false } };
    });
  };

  const updateFreq = (id: string, freq: string) => {
    setSelections(prev => ({ ...prev, [id]: { ...prev[id], frequency: freq } }));
  };

  const toggleCompulsive = (id: string) => {
    setSelections(prev => ({
      ...prev, [id]: { ...prev[id], is_compulsive: !prev[id].is_compulsive },
    }));
  };

  const handleAnalyze = async () => {
    const entries = Object.values(selections);
    if (entries.length === 0) { Alert.alert('Required', 'Select at least one coping strategy.'); return; }
    setSubmitting(true);
    try {
      const res = await api.post(`/emotional-gatekeeper/outlet/${sessionId}/analyze`, { entries });
      setAnalysis(res.data.ai_analysis);
      setStep(1);
    } catch (err) { Alert.alert('Error', 'Analysis failed.'); }
    finally { setSubmitting(false); }
  };

  const groupByNature = (strats: Strategy[]) => {
    const groups: Record<string, Strategy[]> = {};
    strats.forEach(s => {
      const n = s.nature || 'other';
      if (!groups[n]) groups[n] = [];
      groups[n].push(s);
    });
    return groups;
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#10B981" />
        </View>
      </SafeAreaView>
    );
  }

  const renderStep0 = () => {
    const groups = groupByNature(strategies);
    return (
      <View style={s.stepContent}>
        <Text style={s.stepTitle}>Select Your Coping Strategies</Text>
        <Text style={s.stepHint}>Tap to select. Then set frequency and whether it feels compulsive.</Text>
        {Object.entries(groups).map(([nature, strats]) => (
          <View key={nature}>
            <View style={s.natureHeader}>
              <View style={[s.natureDot, { backgroundColor: NATURE_COLORS[nature] || '#6B7280' }]} />
              <Text style={s.natureLabel}>{nature.charAt(0).toUpperCase() + nature.slice(1)}</Text>
            </View>
            {strats.map(st => {
              const sel = selections[st.id];
              return (
                <View key={st.id}>
                  <TouchableOpacity style={[s.stratCard, sel && s.stratCardActive]}
                    onPress={() => toggleStrategy(st.id)}>
                    <View style={[s.checkbox, sel && s.checkboxActive]}>
                      {sel && <Ionicons name="checkmark" size={14} color="#FFF" />}
                    </View>
                    <Text style={[s.stratName, sel && s.stratNameActive]}>{st.name}</Text>
                  </TouchableOpacity>
                  {sel && (
                    <View style={s.selOptions}>
                      <View style={s.freqRow}>
                        {FREQ_OPTIONS.map(f => (
                          <TouchableOpacity key={f.id}
                            style={[s.freqChip, sel.frequency === f.id && { backgroundColor: f.color, borderColor: f.color }]}
                            onPress={() => updateFreq(st.id, f.id)}>
                            <Text style={[s.freqText, sel.frequency === f.id && { color: '#FFF' }]}>{f.label}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                      <TouchableOpacity style={s.compRow} onPress={() => toggleCompulsive(st.id)}>
                        <View style={[s.checkbox, sel.is_compulsive && { backgroundColor: '#EF4444', borderColor: '#EF4444' }]}>
                          {sel.is_compulsive && <Ionicons name="checkmark" size={14} color="#FFF" />}
                        </View>
                        <Text style={s.compText}>Feels compulsive (can't stop easily)</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              );
            })}
          </View>
        ))}
        <TouchableOpacity style={s.nextBtn} onPress={handleAnalyze} disabled={submitting}>
          {submitting ? <ActivityIndicator color="#FFF" /> :
            <><Text style={s.nextBtnText}>Analyze My Outlets</Text><Ionicons name="analytics" size={18} color="#FFF" /></>}
        </TouchableOpacity>
      </View>
    );
  };

  const renderStep1 = () => (
    <View style={s.stepContent}>
      <LinearGradient colors={['#ECFDF5', '#D1FAE5']} style={s.resultCard}>
        <Text style={s.resultTitle}>Outlet Analysis</Text>
        {analysis?.summary && (
          <View style={s.summaryRow}>
            <View style={s.summaryItem}><Text style={s.sumNum}>{analysis.summary.total_strategies}</Text><Text style={s.sumLabel}>Total</Text></View>
            <View style={s.summaryItem}><Text style={[s.sumNum, { color: '#10B981' }]}>{analysis.summary.constructive_count}</Text><Text style={s.sumLabel}>Constructive</Text></View>
            <View style={s.summaryItem}><Text style={[s.sumNum, { color: '#EF4444' }]}>{analysis.summary.destructive_count}</Text><Text style={s.sumLabel}>Destructive</Text></View>
            <View style={s.summaryItem}><Text style={[s.sumNum, { color: '#F59E0B' }]}>{analysis.summary.compulsive_count}</Text><Text style={s.sumLabel}>Compulsive</Text></View>
          </View>
        )}
        {analysis?.balance_score && (
          <View style={s.balanceRow}>
            {Object.entries(analysis.balance_score).map(([k, v]) => (
              <View key={k} style={s.balanceItem}>
                <Text style={s.balanceNum}>{v as number}/10</Text>
                <Text style={s.balanceLabel}>{k}</Text>
              </View>
            ))}
          </View>
        )}
        {analysis?.analysis?.map((a: any, i: number) => (
          <View key={i} style={s.analysisItem}>
            <View style={s.analysisHeader}>
              <View style={[s.natureDot, { backgroundColor: NATURE_COLORS[a.nature] || '#6B7280' }]} />
              <Text style={s.analysisName}>{a.strategy}</Text>
              <View style={[s.assessBadge, { backgroundColor: a.assessment === 'constructive' ? '#10B981' : a.assessment === 'destructive' ? '#EF4444' : '#6B7280' }]}>
                <Text style={s.assessText}>{a.assessment}</Text>
              </View>
            </View>
            <Text style={s.analysisExplanation}>{a.explanation}</Text>
            {a.recommended_alternative && (
              <View style={s.altBox}>
                <Ionicons name="arrow-forward-circle" size={16} color="#059669" />
                <View style={{ flex: 1 }}>
                  <Text style={s.altTitle}>Try instead: {a.recommended_alternative}</Text>
                  <Text style={s.altWhy}>{a.why_alternative}</Text>
                </View>
              </View>
            )}
          </View>
        ))}
        {analysis?.overall_pattern && (
          <View style={s.patternBox}>
            <Ionicons name="bulb" size={18} color="#065F46" />
            <Text style={s.patternText}>{analysis.overall_pattern}</Text>
          </View>
        )}
        {analysis?.top_recommendations?.map((r: string, i: number) => (
          <View key={i} style={s.recItem}>
            <Text style={s.recNum}>{i + 1}</Text>
            <Text style={s.recText}>{r}</Text>
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
        <LinearGradient colors={['#10B981', '#059669']} style={s.header}>
          <TouchableOpacity style={s.backBtn} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Emotional Outlet Analyzer</Text>
          <Text style={s.headerSub}>{step === 0 ? 'Select Your Strategies' : 'AI Analysis Results'}</Text>
        </LinearGradient>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
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
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  stepContent: { padding: 16 },
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  stepHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 16 },
  natureHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, marginBottom: 8 },
  natureDot: { width: 10, height: 10, borderRadius: 5 },
  natureLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase' },
  stratCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: COLORS.border },
  stratCardActive: { borderColor: '#10B981', backgroundColor: '#F0FDF4' },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  checkboxActive: { backgroundColor: '#10B981', borderColor: '#10B981' },
  stratName: { fontSize: 13, color: COLORS.textSecondary, flex: 1 },
  stratNameActive: { color: COLORS.textPrimary, fontWeight: '600' },
  selOptions: { backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10, marginBottom: 8, marginLeft: 32 },
  freqRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  freqChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FFF' },
  freqText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  compRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  compText: { fontSize: 12, color: COLORS.textMuted },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#10B981', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  resultCard: { borderRadius: 16, padding: 20 },
  resultTitle: { fontSize: 20, fontWeight: '800', color: '#065F46', marginBottom: 12 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 16, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, paddingVertical: 12 },
  summaryItem: { alignItems: 'center' },
  sumNum: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary },
  sumLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  balanceRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 16 },
  balanceItem: { alignItems: 'center' },
  balanceNum: { fontSize: 16, fontWeight: '700', color: '#065F46' },
  balanceLabel: { fontSize: 10, color: COLORS.textMuted, textTransform: 'capitalize', marginTop: 2 },
  analysisItem: { backgroundColor: 'rgba(255,255,255,0.5)', borderRadius: 12, padding: 12, marginBottom: 10 },
  analysisHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  analysisName: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  assessBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  assessText: { fontSize: 10, fontWeight: '700', color: '#FFF', textTransform: 'uppercase' },
  analysisExplanation: { fontSize: 12, color: '#065F46', lineHeight: 17 },
  altBox: { flexDirection: 'row', gap: 6, backgroundColor: '#ECFDF5', borderRadius: 8, padding: 10, marginTop: 8 },
  altTitle: { fontSize: 12, fontWeight: '700', color: '#047857' },
  altWhy: { fontSize: 11, color: '#065F46', marginTop: 2 },
  patternBox: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginTop: 12 },
  patternText: { fontSize: 13, color: '#065F46', flex: 1, lineHeight: 18 },
  recItem: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', marginTop: 8 },
  recNum: { fontSize: 14, fontWeight: '800', color: '#059669', width: 20 },
  recText: { fontSize: 13, color: '#047857', flex: 1, lineHeight: 18 },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
});
