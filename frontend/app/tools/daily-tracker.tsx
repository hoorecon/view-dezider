/**
 * /tools/daily-tracker  — Multi-modal entry log (text now; voice/AI later).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';

const FREEDOM_KEYS = ['business', 'financial', 'time', 'health', 'emotional', 'social', 'mission'];
const TEPFI = ['time', 'energy', 'people', 'finance', 'infrastructure'];
const LEVELS = ['self', 'micro', 'macro'];

export default function DailyTrackerScreen() {
  const router = useRouter();
  const [text, setText] = useState('');
  const [activity, setActivity] = useState('');
  const [minutes, setMinutes] = useState('');
  const [linkedFreedoms, setLinkedFreedoms] = useState<string[]>([]);
  const [classification, setClassification] = useState<any>(null);
  const [classifying, setClassifying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [today, setToday] = useState<any>(null);
  const [aalaDelta, setAalaDelta] = useState<{ factor: string; level: string; delta_value: number } | null>(null);

  const loadToday = useCallback(async () => {
    try { const r = await api.get('/daily-tracker/today'); setToday(r.data); } catch { /* ignore */ }
  }, []);
  useEffect(() => { loadToday(); }, [loadToday]);

  const aiClassify = async () => {
    if (!text.trim()) return showAlert('Empty', 'Type or paste an entry first.');
    try { setClassifying(true);
      const r = await api.post('/daily-tracker/classify', { text });
      const c = r.data.classification;
      setClassification(c);
      if (c?.minutes && !minutes) setMinutes(String(c.minutes));
      if (c?.freedoms?.length) setLinkedFreedoms(prev => Array.from(new Set([...prev, ...c.freedoms])));
      if (c?.factors?.length && c?.sign && !aalaDelta) {
        setAalaDelta({ factor: c.factors[0], level: 'self', delta_value: c.sign * 1.0 });
      }
    } catch (e: any) { showAlert('Classify failed', e?.response?.data?.detail || e.message); }
    finally { setClassifying(false); }
  };

  const submit = async () => {
    if (!text.trim()) return showAlert('Empty', 'Add some text first.');
    try { setSubmitting(true);
      const body: any = {
        text, source: 'text',
        activity: activity || undefined,
        minutes: minutes ? parseInt(minutes, 10) : undefined,
        linked_freedoms: linkedFreedoms,
        aala_deltas: aalaDelta ? [aalaDelta] : [],
      };
      await api.post('/daily-tracker/entries', body);
      setText(''); setActivity(''); setMinutes(''); setLinkedFreedoms([]); setClassification(null); setAalaDelta(null);
      loadToday();
      showAlert('Logged', 'Entry recorded · Time log + AALA updated.');
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setSubmitting(false); }
  };

  const toggleFr = (k: string) => setLinkedFreedoms(p => p.includes(k) ? p.filter(x => x !== k) : [...p, k]);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Daily Tracker</Text>
          <Text style={s.subtitle}>What did you do? Log it once, AALA + LDC update automatically</Text>
        </View>
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 100 }}>
          <View style={s.card}>
            <Text style={s.fieldLabel}>What just happened?</Text>
            <TextInput
              style={[s.input, { minHeight: 100 }]} multiline
              value={text} onChangeText={setText}
              placeholder="e.g. Closed deal with Bharat ₹50k revenue, 2 hours invested"
              placeholderTextColor={COLORS.textMuted}
            />
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 8 }}>
              <TouchableOpacity onPress={aiClassify} disabled={classifying} style={[s.btnGhost, { flex: 1 }]}>
                {classifying ? <ActivityIndicator color={COLORS.primary} /> : (
                  <>
                    <Ionicons name="sparkles" size={14} color={COLORS.primary} />
                    <Text style={s.btnGhostText}>AI classify</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
            {classification && (
              <View style={s.aiBox}>
                <Text style={s.aiTag}>engine: {classification.engine} · confidence {Math.round((classification.confidence || 0) * 100)}%</Text>
                <Text style={s.aiText}>Factors: {(classification.factors || []).join(', ') || '—'}</Text>
                <Text style={s.aiText}>Freedoms: {(classification.freedoms || []).join(', ') || '—'}</Text>
                <Text style={s.aiText}>Sign: {classification.sign > 0 ? '📈 positive' : classification.sign < 0 ? '📉 negative' : 'neutral'} · minutes: {classification.minutes ?? '—'}</Text>
              </View>
            )}
          </View>

          <View style={s.card}>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 2 }}>
                <Text style={s.fieldLabel}>Activity label</Text>
                <TextInput style={s.input} value={activity} onChangeText={setActivity} placeholder="Client call" placeholderTextColor={COLORS.textMuted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.fieldLabel}>Minutes</Text>
                <TextInput style={s.input} keyboardType="numeric" value={minutes} onChangeText={setMinutes} placeholder="30" placeholderTextColor={COLORS.textMuted} />
              </View>
            </View>

            <Text style={s.fieldLabel}>Linked freedoms</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
              {FREEDOM_KEYS.map(k => (
                <TouchableOpacity key={k} testID={`dt-fr-${k}`} onPress={() => toggleFr(k)} style={[s.chip, linkedFreedoms.includes(k) && s.chipActive]}>
                  <Text style={[s.chipText, linkedFreedoms.includes(k) && s.chipTextActive]}>{k}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.fieldLabel}>AALA delta (optional)</Text>
            <Text style={s.helper}>Auto-updates one resource cell on submit.</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
              <View style={{ flex: 1 }}>
                <Text style={s.miniLabel}>Factor</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                  {TEPFI.map(f => (
                    <TouchableOpacity key={f} onPress={() => setAalaDelta(p => ({ factor: f, level: p?.level || 'self', delta_value: p?.delta_value || 1 }))} style={[s.miniChip, aalaDelta?.factor === f && s.chipActive]}>
                      <Text style={[s.miniChipText, aalaDelta?.factor === f && s.chipTextActive]}>{f}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
              <View style={{ flex: 1 }}>
                <Text style={s.miniLabel}>Level</Text>
                <View style={{ flexDirection: 'row', gap: 4 }}>
                  {LEVELS.map(l => (
                    <TouchableOpacity key={l} onPress={() => setAalaDelta(p => p ? ({ ...p, level: l }) : { factor: 'time', level: l, delta_value: 1 })} style={[s.miniChip, aalaDelta?.level === l && s.chipActive]}>
                      <Text style={[s.miniChipText, aalaDelta?.level === l && s.chipTextActive]}>{l}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.miniLabel}>Delta (-10…10)</Text>
                <TextInput style={s.input} keyboardType="numeric" value={String(aalaDelta?.delta_value ?? '')} onChangeText={v => setAalaDelta(p => p ? ({ ...p, delta_value: parseFloat(v) || 0 }) : null)} placeholder="+1" placeholderTextColor={COLORS.textMuted} />
              </View>
            </View>
          </View>

          <TouchableOpacity testID="dt-submit" onPress={submit} disabled={submitting} style={[s.primary, { opacity: submitting ? 0.6 : 1 }]}>
            {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>Log entry</Text>}
          </TouchableOpacity>

          {today && today.entries?.length > 0 && (
            <View style={[s.card, { marginTop: 14 }]}>
              <Text style={s.fieldLabel}>Today · {today.total_minutes} min total</Text>
              {Object.entries(today.by_freedom_minutes || {}).map(([k, v]: any) => (
                <Text key={k} style={s.todayRow}>• {k}: {v} min</Text>
              ))}
              {today.entries.slice(0, 5).map((e: any) => (
                <Text key={e.entry_id} style={s.todayEntry}>— {e.activity || '(no label)'}{e.minutes ? ` · ${e.minutes} min` : ''}</Text>
              ))}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
  card: { backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 },
  miniLabel: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase', marginTop: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  chipActive: { backgroundColor: COLORS.primary + '22', borderColor: COLORS.primary },
  chipText: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600', textTransform: 'capitalize' },
  chipTextActive: { color: COLORS.primary, fontWeight: '700' },
  miniChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  miniChipText: { fontSize: 10, color: COLORS.textSecondary, fontWeight: '600', textTransform: 'capitalize' },
  btnGhost: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, backgroundColor: '#FFF' },
  btnGhostText: { color: COLORS.primary, fontSize: 13, fontWeight: '700' },
  aiBox: { marginTop: 8, padding: 10, borderRadius: 8, backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: '#DDD6FE' },
  aiTag: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600', marginBottom: 4 },
  aiText: { fontSize: 12, color: COLORS.textPrimary, marginTop: 2 },
  primary: { backgroundColor: COLORS.primary, paddingVertical: 13, borderRadius: 10, alignItems: 'center' },
  primaryText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  todayRow: { fontSize: 12, color: COLORS.textPrimary, marginTop: 4 },
  todayEntry: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
});
