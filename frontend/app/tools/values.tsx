/**
 * Values Tracker — user-facing module screen.
 *
 * v3.25 SCOPE NOTE: This screen ships the **My Values** and **AI Advisor** tabs.
 * The 5-question Daily Reflection moves under the existing
 * `Consciousness Diary → Wellness` tab (separate follow-up) so reflections
 * can be captured against ANY of: org-values, eg-trap, eg-loop, eg-limitation,
 * solution-finder — backed by the same `/api/values/reflect` endpoint.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';

interface Principle {
  id: string; code: string; name: string; short?: string; body: string; bullets?: string[]; order: number;
  platform_default?: boolean; org_id?: string | null;
}
interface AdvisorPick { code: string; alignment_score: number; why: string; do?: string; dont?: string; }

export default function ValuesScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<'principles' | 'advisor'>('principles');
  const [principles, setPrinciples] = useState<Principle[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [situation, setSituation] = useState('');
  const [advising, setAdvising] = useState(false);
  const [advisorResult, setAdvisorResult] = useState<AdvisorPick[] | null>(null);

  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get('/values/principles'); setPrinciples(data?.principles || []); }
    finally { setLoading(false); }
  };

  const askAdvisor = async () => {
    if (!situation.trim()) return;
    setAdvising(true); setAdvisorResult(null);
    try {
      const { data } = await api.post('/values/ai-advisor', { situation: situation.trim(), use_top_n: 3 });
      setAdvisorResult(data?.picks || []);
    } catch (e: any) {
      setAdvisorResult([]);
    } finally { setAdvising(false); }
  };

  const principleByCode = (c: string) => principles.find(p => p.code === c);

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={s.title}>Values Tracker</Text>
        <Text style={s.subtitle}>8 Collaboration Principles · ongoingly editable by admin</Text>
      </View>
      <View style={s.tabs}>
        <TouchableOpacity style={[s.tab, tab === 'principles' && s.tabActive]} onPress={() => setTab('principles')}>
          <Text style={[s.tabText, tab === 'principles' && s.tabTextActive]}>Principles</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.tab, tab === 'advisor' && s.tabActive]} onPress={() => setTab('advisor')}>
          <Text style={[s.tabText, tab === 'advisor' && s.tabTextActive]}>AI Advisor</Text>
        </TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {tab === 'principles' && (
          loading ? <ActivityIndicator /> : (
            principles.map((p, idx) => (
              <View key={p.id} style={s.card}>
                <TouchableOpacity style={s.cardHeader} onPress={() => setExpanded(e => ({ ...e, [p.id]: !e[p.id] }))}>
                  <View style={s.idxBubble}><Text style={s.idxText}>{p.order || idx + 1}</Text></View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.pName}>{p.name}</Text>
                    {p.short ? <Text style={s.pShort}>{p.short}</Text> : null}
                  </View>
                  <Ionicons name={expanded[p.id] ? 'chevron-up' : 'chevron-down'} size={18} color="#475569" />
                </TouchableOpacity>
                {expanded[p.id] && (
                  <View style={s.cardBody}>
                    <Text style={s.pBody}>{p.body}</Text>
                    {p.bullets?.map((b, i) => (
                      <View key={i} style={s.bulletRow}>
                        <Text style={s.bulletDot}>•</Text>
                        <Text style={s.bulletText}>{b}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            ))
          )
        )}
        {tab === 'advisor' && (
          <View>
            <Text style={s.advLabel}>Describe a challenging situation</Text>
            <TextInput
              style={s.advInput}
              value={situation}
              onChangeText={setSituation}
              multiline
              placeholder="e.g. My peer didn't show up to the planned 10am call and went silent..."
              placeholderTextColor="#94A3B8"
            />
            <TouchableOpacity style={s.advBtn} onPress={askAdvisor} disabled={advising || !situation.trim()}>
              {advising ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="sparkles" size={16} color="#FFF" /><Text style={s.advBtnText}>Get top-3 alignment guidance</Text></>)}
            </TouchableOpacity>
            {advisorResult && advisorResult.map((r, i) => {
              const p = principleByCode(r.code);
              return (
                <View key={i} style={s.advResultCard}>
                  <View style={s.advResultHead}>
                    <Text style={s.advResultName}>{p?.name || r.code}</Text>
                    <View style={[s.scoreBadge, { backgroundColor: r.alignment_score >= 7 ? '#10B981' : r.alignment_score >= 4 ? '#F59E0B' : '#EF4444' }]}>
                      <Text style={s.scoreText}>{r.alignment_score}/10</Text>
                    </View>
                  </View>
                  <Text style={s.advWhy}>{r.why}</Text>
                  {r.do && <View style={s.doRow}><Ionicons name="checkmark-circle" size={14} color="#10B981" /><Text style={s.doText}>{r.do}</Text></View>}
                  {r.dont && <View style={s.doRow}><Ionicons name="close-circle" size={14} color="#EF4444" /><Text style={s.dontText}>{r.dont}</Text></View>}
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { backgroundColor: '#003087', padding: 16, paddingBottom: 18 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 22, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  tabs: { flexDirection: 'row', backgroundColor: '#FFF', borderBottomWidth: 1, borderColor: '#E2E8F0' },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderColor: '#003087' },
  tabText: { fontSize: 13, fontWeight: '600', color: '#64748B' },
  tabTextActive: { color: '#003087', fontWeight: '800' },
  card: { backgroundColor: '#FFF', borderRadius: 12, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0', overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12 },
  idxBubble: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#003087', alignItems: 'center', justifyContent: 'center' },
  idxText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
  pName: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  pShort: { fontSize: 12, color: '#475569', marginTop: 2 },
  cardBody: { padding: 12, paddingTop: 0, borderTopWidth: 1, borderColor: '#F1F5F9' },
  pBody: { fontSize: 13, color: '#0F172A', lineHeight: 19, marginTop: 8 },
  bulletRow: { flexDirection: 'row', gap: 6, marginTop: 6 },
  bulletDot: { color: '#64748B' },
  bulletText: { flex: 1, fontSize: 12, color: '#334155', lineHeight: 18 },
  advLabel: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginBottom: 6 },
  advInput: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, padding: 12, fontSize: 14, color: '#0F172A', minHeight: 100, textAlignVertical: 'top' },
  advBtn: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8, backgroundColor: '#003087', borderRadius: 12, paddingVertical: 12, marginTop: 12 },
  advBtnText: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  advResultCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginTop: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  advResultHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  advResultName: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  scoreBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  scoreText: { color: '#FFF', fontWeight: '800', fontSize: 12 },
  advWhy: { fontSize: 13, color: '#334155', marginTop: 8, lineHeight: 18 },
  doRow: { flexDirection: 'row', gap: 6, marginTop: 6, alignItems: 'flex-start' },
  doText: { flex: 1, fontSize: 12, color: '#065F46', lineHeight: 17 },
  dontText: { flex: 1, fontSize: 12, color: '#7F1D1D', lineHeight: 17 },
});
