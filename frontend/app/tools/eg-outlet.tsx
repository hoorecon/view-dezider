import React, { useState, useEffect, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Alert } from '../../src/utils/crossAlert';
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
  physical: '#EF4444', mental: '#3B82F6', emotional: '#F59E0B', energy: '#8B5CF6', other: '#6B7280',
};
const NATURE_LABELS: Record<string, string> = {
  physical: 'Physical', mental: 'Mental', emotional: 'Emotional', energy: 'Energy', other: 'Other',
};

interface Strategy {
  id: string; name: string; nature: string; default_constructive: boolean | null;
}
interface Selection {
  strategy_id: string; frequency: string; is_compulsive: boolean;
}

// Deterministic shuffle so the mixed order is stable across re-renders.
const seededShuffle = (arr: Strategy[]) => {
  const a = [...arr];
  let seed = 42;
  const rnd = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

export default function EGOutletScreen() {
  const router = useRouter();
  const goBack = () => { if (router.canGoBack?.()) router.back(); else router.replace('/tools/emotional-gatekeeper' as any); };
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selections, setSelections] = useState<Record<string, Selection>>({});
  const [analysis, setAnalysis] = useState<any>(null);

  // Resume a completed session: show the saved analysis.
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const { data } = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
        const o = data?.outlet_reflection;
        if (o?.ai_analysis) { setAnalysis(o.ai_analysis); setStep(1); }
      } catch { /* ignore */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/emotional-gatekeeper/outlet/strategies');
        setStrategies(res.data.strategies || []);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    })();
  }, []);

  // Mixed (shuffled) list — exclude the "other" free-text catch-all from the grid.
  const mixed = useMemo(
    () => seededShuffle(strategies.filter(st => st.nature !== 'other')),
    [strategies],
  );

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

  const selectedCount = Object.keys(selections).length;

  const handleAnalyze = async () => {
    const entries = Object.values(selections);
    if (entries.length === 0) { Alert.alert('Required', 'Select at least one outlet you use.'); return; }
    setSubmitting(true);
    try {
      const res = await api.post(`/emotional-gatekeeper/outlet/${sessionId}/analyze`, { entries });
      setAnalysis(res.data.ai_analysis);
      setStep(1);
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || 'Analysis failed. Please try again.';
      Alert.alert('Error', msg);
    }
    finally { setSubmitting(false); }
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

  const renderStep0 = () => (
    <View style={s.stepContent} testID="outlet-step-select">
      <Text style={s.stepTitle}>Which outlets do you use?</Text>
      <Text style={s.stepHint}>
        Tap every outlet you reach for when emotions run high — the healthy and the not-so-healthy.
        We&apos;ll reveal where your energy really goes.
      </Text>

      {/* Legend */}
      <View style={s.legendRow}>
        {(['physical', 'mental', 'emotional', 'energy'] as const).map(n => (
          <View key={n} style={s.legendItem}>
            <View style={[s.legendDot, { backgroundColor: NATURE_COLORS[n] }]} />
            <Text style={s.legendText}>{NATURE_LABELS[n]}</Text>
          </View>
        ))}
      </View>

      {mixed.map(st => {
        const sel = selections[st.id];
        const c = NATURE_COLORS[st.nature] || '#6B7280';
        return (
          <View key={st.id}>
            <TouchableOpacity
              testID={`outlet-option-${st.id}`}
              style={[s.stratCard, { borderLeftColor: c, borderLeftWidth: 4 }, sel && s.stratCardActive]}
              onPress={() => toggleStrategy(st.id)}>
              <View style={[s.checkbox, sel && { backgroundColor: c, borderColor: c }]}>
                {sel && <Ionicons name="checkmark" size={14} color="#FFF" />}
              </View>
              <Text style={[s.stratName, sel && s.stratNameActive]}>{st.name}</Text>
            </TouchableOpacity>
            {sel && (
              <View style={s.selOptions}>
                <View style={s.freqRow}>
                  {FREQ_OPTIONS.map(f => (
                    <TouchableOpacity key={f.id}
                      testID={`outlet-freq-${st.id}-${f.id}`}
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
                  <Text style={s.compText}>Feels compulsive (can&apos;t stop easily)</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        );
      })}

      <TouchableOpacity testID="outlet-analyze-btn" style={s.nextBtn} onPress={handleAnalyze} disabled={submitting}>
        {submitting ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Reveal My Outlet Profile{selectedCount ? ` (${selectedCount})` : ''}</Text><Ionicons name="sparkles" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  const renderBreakdown = () => {
    const bd: Record<string, number> = analysis?.group_breakdown || {};
    const order = ['physical', 'mental', 'emotional', 'energy'];
    const entries = order.filter(k => k in bd);
    if (entries.length === 0) return null;
    return (
      <View style={s.breakdownCard} testID="outlet-breakdown">
        <Text style={s.breakdownTitle}>Where Your Energy Goes</Text>
        {entries.map(k => (
          <View key={k} style={s.barRow}>
            <Text style={s.barLabel}>{NATURE_LABELS[k]}</Text>
            <View style={s.barTrack}>
              <View style={[s.barFill, { width: `${bd[k]}%`, backgroundColor: NATURE_COLORS[k] }]} />
            </View>
            <Text style={s.barPct}>{bd[k]}%</Text>
          </View>
        ))}
      </View>
    );
  };

  const renderModes = () => {
    const p = analysis?.primary_mode, sec = analysis?.secondary_mode;
    if (!p) return null;
    return (
      <View style={s.modesRow} testID="outlet-top-modes">
        <View style={[s.modeChip, { borderColor: NATURE_COLORS[p] }]}>
          <Text style={s.modeRank}>PRIMARY MODE</Text>
          <View style={s.modeNameRow}>
            <View style={[s.natureDot, { backgroundColor: NATURE_COLORS[p] }]} />
            <Text style={[s.modeName, { color: NATURE_COLORS[p] }]}>{NATURE_LABELS[p]}</Text>
          </View>
        </View>
        {sec ? (
          <View style={[s.modeChip, { borderColor: NATURE_COLORS[sec] }]}>
            <Text style={s.modeRank}>SECONDARY MODE</Text>
            <View style={s.modeNameRow}>
              <View style={[s.natureDot, { backgroundColor: NATURE_COLORS[sec] }]} />
              <Text style={[s.modeName, { color: NATURE_COLORS[sec] }]}>{NATURE_LABELS[sec]}</Text>
            </View>
          </View>
        ) : null}
      </View>
    );
  };

  const renderStep1 = () => (
    <View style={s.stepContent} testID="outlet-results">
      <LinearGradient colors={['#ECFDF5', '#D1FAE5']} style={s.resultCard}>
        <Text style={s.resultTitle}>Your Outlet Profile</Text>

        {renderModes()}
        {renderBreakdown()}

        {analysis?.mode_insight && (
          <View style={s.insightBox}>
            <Ionicons name="bulb" size={18} color="#065F46" />
            <Text style={s.insightText}>{analysis.mode_insight}</Text>
          </View>
        )}

        {analysis?.replacement_activities?.length > 0 && (
          <View style={s.swapSection}>
            <Text style={s.swapHeader}>5 Healthier Swaps — same outlet, better effect</Text>
            {analysis.replacement_activities.map((a: any, i: number) => {
              const c = NATURE_COLORS[a.group] || '#6B7280';
              return (
                <View key={i} style={[s.swapCard, { borderLeftColor: c }]} testID={`outlet-swap-${i}`}>
                  <View style={s.swapTopRow}>
                    <View style={[s.groupPill, { backgroundColor: c }]}>
                      <Text style={s.groupPillText}>{NATURE_LABELS[a.group] || a.group}</Text>
                    </View>
                    <Text style={s.swapActivity}>{a.activity}</Text>
                  </View>
                  {a.replaces ? <Text style={s.swapReplaces}>Replaces: {a.replaces}</Text> : null}
                  {a.why ? <Text style={s.swapWhy}>{a.why}</Text> : null}
                </View>
              );
            })}
          </View>
        )}

        {analysis?.overall_pattern && (
          <View style={s.patternBox}>
            <Text style={s.patternText}>{analysis.overall_pattern}</Text>
          </View>
        )}
        {analysis?.encouragement && (
          <Text style={s.encourageText}>“{analysis.encouragement}”</Text>
        )}
      </LinearGradient>

      <TouchableOpacity testID="outlet-done-btn" style={s.doneBtn} onPress={() => router.push('/tools/emotional-gatekeeper' as any)}>
        <Text style={s.doneBtnText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <LinearGradient colors={['#10B981', '#059669']} style={s.header}>
          <TouchableOpacity testID="outlet-back-btn" style={s.backBtn} onPress={goBack}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Emotional Outlet Analyzer</Text>
          <Text style={s.headerSub}>{step === 0 ? 'Select Your Outlets' : 'Your Profile & Swaps'}</Text>
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
  stepHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 14, lineHeight: 18 },
  legendRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 14, backgroundColor: '#FFF', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: COLORS.border },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendDot: { width: 9, height: 9, borderRadius: 5 },
  legendText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  natureDot: { width: 10, height: 10, borderRadius: 5 },
  stratCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: COLORS.border },
  stratCardActive: { backgroundColor: '#F0FDF4' },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  stratName: { fontSize: 13, color: COLORS.textSecondary, flex: 1 },
  stratNameActive: { color: COLORS.textPrimary, fontWeight: '600' },
  selOptions: { backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10, marginBottom: 8, marginLeft: 16 },
  freqRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  freqChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FFF' },
  freqText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  compRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  compText: { fontSize: 12, color: COLORS.textMuted },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#10B981', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  resultCard: { borderRadius: 16, padding: 20 },
  resultTitle: { fontSize: 20, fontWeight: '800', color: '#065F46', marginBottom: 14 },

  modesRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  modeChip: { flex: 1, backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 2 },
  modeRank: { fontSize: 9, fontWeight: '800', color: COLORS.textMuted, letterSpacing: 0.5, marginBottom: 4 },
  modeNameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  modeName: { fontSize: 16, fontWeight: '800' },

  breakdownCard: { backgroundColor: 'rgba(255,255,255,0.7)', borderRadius: 12, padding: 14, marginBottom: 16 },
  breakdownTitle: { fontSize: 13, fontWeight: '700', color: '#065F46', marginBottom: 10 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  barLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary, width: 70 },
  barTrack: { flex: 1, height: 12, borderRadius: 6, backgroundColor: '#E5E7EB', overflow: 'hidden' },
  barFill: { height: 12, borderRadius: 6 },
  barPct: { fontSize: 12, fontWeight: '800', color: COLORS.textPrimary, width: 38, textAlign: 'right' },

  insightBox: { flexDirection: 'row', gap: 8, backgroundColor: 'rgba(255,255,255,0.7)', borderRadius: 12, padding: 14, marginBottom: 16 },
  insightText: { fontSize: 13, color: '#065F46', flex: 1, lineHeight: 19 },

  swapSection: { marginBottom: 8 },
  swapHeader: { fontSize: 14, fontWeight: '800', color: '#065F46', marginBottom: 10 },
  swapCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderLeftWidth: 4 },
  swapTopRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  groupPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  groupPillText: { fontSize: 9, fontWeight: '800', color: '#FFF', textTransform: 'uppercase' },
  swapActivity: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  swapReplaces: { fontSize: 11, color: '#B45309', fontWeight: '600', marginBottom: 2 },
  swapWhy: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },

  patternBox: { backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 12, padding: 14, marginTop: 8 },
  patternText: { fontSize: 13, color: '#065F46', lineHeight: 19 },
  encourageText: { fontSize: 14, fontStyle: 'italic', fontWeight: '600', color: '#047857', textAlign: 'center', marginTop: 14 },

  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 10 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
});
