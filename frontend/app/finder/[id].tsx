/**
 * /finder/[id] — DeciderApp "Finder" run + Top-N results.
 *
 * For a decision cloned from a DeciderApp (kind='app'), after the user sets
 * Expected values (Step 2), classifies Mandatory/Optional (Step 3) and
 * prioritizes (Step 4), this screen auto-filters + auto-assesses ALL options
 * and shows the Top-N by Overall %. Config defaults come from Admin; the user
 * can override min/max/Top-N, match rule and the assessment engine per run.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

type Ranked = { option_id: string; name?: string; worth_percentage: number; ai_rationale?: string };

export default function FinderScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [title, setTitle] = useState('Finder');
  const [minOpt, setMinOpt] = useState('3');
  const [maxOpt, setMaxOpt] = useState('15');
  const [topN, setTopN] = useState('5');
  const [matchRule, setMatchRule] = useState<'all' | 'any'>('all');
  const [engine, setEngine] = useState<'deterministic' | 'llm'>('deterministic');
  const [result, setResult] = useState<any>(null);
  const [totalOptions, setTotalOptions] = useState(0);

  const loadConfig = useCallback(async () => {
    try {
      const [cfgR, decR] = await Promise.all([
        api.get(`/decisions/${id}/finder/config`),
        api.get(`/decisions/${id}`).catch(() => null),
      ]);
      const c = cfgR.data.config || {};
      setMinOpt(String(c.min_options ?? 3));
      setMaxOpt(String(c.max_options ?? 15));
      setTopN(String(c.top_n ?? 5));
      setMatchRule(c.match_rule === 'any' ? 'any' : 'all');
      setEngine(c.engine === 'llm' ? 'llm' : 'deterministic');
      setTotalOptions(cfgR.data.total_options || 0);
      if (decR?.data?.title) setTitle(decR.data.title);
    } catch (e: any) {
      showAlert('Could not load', e?.response?.data?.detail || 'Try again.');
    } finally { setLoading(false); }
  }, [id]);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const run = async () => {
    setRunning(true);
    try {
      const r = await api.post(`/decisions/${id}/finder/run`, {
        min_options: parseInt(minOpt) || 3,
        max_options: parseInt(maxOpt) || 15,
        top_n: parseInt(topN) || 5,
        match_rule: matchRule,
        engine,
      });
      setResult(r.data);
      if (r.data?.llm?.out_of_credits) {
        showAlert('AI credits low', 'Some options were assessed without AI (deterministic fallback). Top up to use full AI assessment.');
      }
    } catch (e: any) {
      showAlert('Finder failed', e?.response?.data?.detail || 'Try again.');
    } finally { setRunning(false); }
  };

  const STAGE_LABEL: Record<string, string> = {
    mandatory: 'Filtered by your Mandatory factors',
    'mandatory+optional': 'Filtered by Mandatory + Optional factors',
    relaxed_all: 'Too few mandatory matches — searched all options',
  };

  const barColor = (pct: number) => (pct >= 75 ? '#16A34A' : pct >= 50 ? '#D97706' : '#DC2626');

  if (loading) {
    return <SafeAreaView style={s.root}><ActivityIndicator color="#4F46E5" style={{ marginTop: 60 }} /></SafeAreaView>;
  }

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, `/prr/${id}`)}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title} numberOfLines={1}>{title}</Text>
          <Text style={s.sub}>Finder · auto-rank the best matches</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={s.body}>
        {/* Settings */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Finder settings</Text>
          <Text style={s.help}>Searching {totalOptions} options. Adjust below or just run with the defaults.</Text>
          <View style={s.row3}>
            <View style={s.num}><Text style={s.numLabel}>Min</Text>
              <TextInput style={s.numInput} value={minOpt} onChangeText={setMinOpt} keyboardType="numeric" /></View>
            <View style={s.num}><Text style={s.numLabel}>Max</Text>
              <TextInput style={s.numInput} value={maxOpt} onChangeText={setMaxOpt} keyboardType="numeric" /></View>
            <View style={s.num}><Text style={s.numLabel}>Top N</Text>
              <TextInput style={s.numInput} value={topN} onChangeText={setTopN} keyboardType="numeric" /></View>
          </View>
          <Text style={s.fieldLabel}>Sub-factor match</Text>
          <View style={s.seg}>
            {(['all', 'any'] as const).map((m) => (
              <TouchableOpacity key={m} style={[s.segBtn, matchRule === m && s.segOn]} onPress={() => setMatchRule(m)}>
                <Text style={[s.segText, matchRule === m && s.segTextOn]}>{m === 'all' ? 'Match ALL' : 'Match ANY'}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={s.fieldLabel}>Assessment engine</Text>
          <View style={s.seg}>
            {(['deterministic', 'llm'] as const).map((m) => (
              <TouchableOpacity key={m} style={[s.segBtn, engine === m && s.segOn]} onPress={() => setEngine(m)}>
                <Text style={[s.segText, engine === m && s.segTextOn]}>{m === 'deterministic' ? '⚡ Fast (rules)' : '🤖 AI (LLM)'}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity style={s.runBtn} onPress={run} disabled={running}>
            {running ? <ActivityIndicator color="#FFF" /> : (
              <><Ionicons name="search" size={18} color="#FFF" /><Text style={s.runText}>Run Finder</Text></>
            )}
          </TouchableOpacity>
        </View>

        {/* Results */}
        {result && (
          <View style={s.card}>
            <Text style={s.cardTitle}>Top {result.top?.length || 0} matches</Text>
            <View style={s.funnelRow}>
              <Ionicons name="funnel" size={13} color="#64748B" />
              <Text style={s.funnel}>{STAGE_LABEL[result.stage] || result.stage} · {result.survivors}/{result.total_options} shortlisted</Text>
            </View>
            {(result.top || []).length === 0 ? (
              <Text style={s.empty}>No options matched. Loosen your expected values or switch match to ANY.</Text>
            ) : (result.top as Ranked[]).map((r, i) => (
              <View key={r.option_id} style={s.resRow}>
                <View style={s.rank}><Text style={s.rankText}>{i + 1}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={s.resName} numberOfLines={2}>{r.name}</Text>
                  {!!r.ai_rationale && <Text style={s.resWhy} numberOfLines={2}>{r.ai_rationale}</Text>}
                  <View style={s.barTrack}>
                    <View style={[s.barFill, { width: `${Math.max(2, r.worth_percentage)}%`, backgroundColor: barColor(r.worth_percentage) }]} />
                  </View>
                </View>
                <Text style={[s.pct, { color: barColor(r.worth_percentage) }]}>{r.worth_percentage.toFixed(1)}%</Text>
              </View>
            ))}
            <TouchableOpacity style={s.openBtn} onPress={() => router.push(`/prr/${id}?step=7` as any)}>
              <Ionicons name="options-outline" size={16} color="#4F46E5" />
              <Text style={s.openText}>Open full comparison (Step 7)</Text>
            </TouchableOpacity>
          </View>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  backBtn: { padding: 4 },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 12, color: '#64748B', marginTop: 1 },
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 14 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 6 },
  help: { fontSize: 12, color: '#64748B', marginBottom: 12 },
  row3: { flexDirection: 'row', gap: 10 },
  num: { flex: 1 },
  numLabel: { fontSize: 11.5, fontWeight: '700', color: '#475569', marginBottom: 4 },
  numInput: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', paddingVertical: 9, textAlign: 'center', fontSize: 15, fontWeight: '700', color: '#0F172A' },
  fieldLabel: { fontSize: 11.5, fontWeight: '700', color: '#475569', marginTop: 14, marginBottom: 6 },
  seg: { flexDirection: 'row', gap: 8 },
  segBtn: { flex: 1, paddingVertical: 9, borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF', alignItems: 'center' },
  segOn: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  segText: { fontSize: 12.5, fontWeight: '700', color: '#475569' },
  segTextOn: { color: '#FFF' },
  runBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#4F46E5', borderRadius: 12, paddingVertical: 14, marginTop: 18 },
  runText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  funnelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  funnel: { flex: 1, fontSize: 11.5, color: '#64748B', fontWeight: '600' },
  empty: { textAlign: 'center', color: '#94A3B8', paddingVertical: 16 },
  resRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  rank: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#EEF2FF', alignItems: 'center', justifyContent: 'center' },
  rankText: { fontSize: 13, fontWeight: '900', color: '#4F46E5' },
  resName: { fontSize: 13.5, fontWeight: '700', color: '#0F172A' },
  resWhy: { fontSize: 11.5, color: '#64748B', marginTop: 2 },
  barTrack: { height: 6, borderRadius: 3, backgroundColor: '#F1F5F9', marginTop: 6, overflow: 'hidden' },
  barFill: { height: 6, borderRadius: 3 },
  pct: { fontSize: 15, fontWeight: '900', minWidth: 54, textAlign: 'right' },
  openBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 14, paddingVertical: 10 },
  openText: { fontSize: 13, fontWeight: '700', color: '#4F46E5' },
});
