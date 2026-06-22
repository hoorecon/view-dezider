/**
 * /tools/expert-net/recommend?booking_id=…  — Expert recommends a Solution Store item
 *
 * Auto-creates a CTT task (and optionally a lifestyle routine) on the user's
 * account. Backend: POST /api/expert-net/bookings/{id}/recommend
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Switch, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';
import { safeBack } from '../../../src/utils/navigation';

export default function ExpertRecommendScreen() {
  const router = useRouter();
  const { booking_id, user_name } = useLocalSearchParams();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState<any | null>(null);
  const [note, setNote] = useState('');
  const [createCtt, setCreateCtt] = useState(true);
  const [createRoutine, setCreateRoutine] = useState(false);
  const [routineFreq, setRoutineFreq] = useState<'daily' | 'weekdays' | 'weekly' | 'custom'>('weekly');
  const [submitting, setSubmitting] = useState(false);

  const search = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/solutions-store/solutions', { params: { q: query, limit: 30 } });
      setItems(r.data?.items || r.data || []);
    } catch (e: any) { showAlert('Search failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [query]);
  useEffect(() => { search(); }, []);

  const submit = async () => {
    if (!picked) return showAlert('Required', 'Please pick a solution');
    try { setSubmitting(true);
      await api.post(`/expert-net/bookings/${booking_id}/recommend`, {
        booking_id,
        solution_id: picked.solution_id,
        note: note || undefined,
        create_ctt_task: createCtt,
        create_lifestyle_routine: createRoutine,
        routine_frequency: routineFreq,
      });
      showAlert('Recommended', `Sent to ${user_name || 'user'}.${createCtt ? ' CTT task created.' : ''}${createRoutine ? ' Routine created.' : ''}`);
      safeBack(router);
    } catch (e: any) { showAlert('Recommend failed', e?.response?.data?.detail || e.message); }
    finally { setSubmitting(false); }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={{ padding: 4 }}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Recommend a solution</Text>
        <View style={{ width: 22 }} />
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 100 }}>
          <View style={styles.searchRow}>
            <Ionicons name="search" size={16} color={COLORS.textMuted} />
            <TextInput
              style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary }}
              placeholder="Search Solutions Store…"
              placeholderTextColor={COLORS.textMuted}
              value={query}
              onChangeText={setQuery}
              onSubmitEditing={search}
            />
            <TouchableOpacity onPress={search}><Text style={{ color: COLORS.primary, fontWeight: '700' }}>Go</Text></TouchableOpacity>
          </View>

          {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 20 }} /> : (
            <ScrollView horizontal style={{ marginBottom: 14 }} showsHorizontalScrollIndicator={false}>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {items.slice(0, 30).map(s => (
                  <TouchableOpacity
                    key={s.solution_id}
                    onPress={() => setPicked(s)}
                    style={[styles.solCard, picked?.solution_id === s.solution_id && { borderColor: COLORS.primary, borderWidth: 2, backgroundColor: COLORS.primary + '12' }]}
                  >
                    <Text style={styles.solName} numberOfLines={2}>{s.name || s.title}</Text>
                    {s.type && <Text style={styles.solType}>{s.type}</Text>}
                    {s.price_inr ? <Text style={styles.solPrice}>₹{s.price_inr}</Text> : <Text style={styles.solPrice}>Free</Text>}
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          )}

          {picked && (
            <View style={styles.card}>
              <Text style={styles.sectionH}>Selected</Text>
              <Text style={styles.solName}>{picked.name || picked.title}</Text>
              {!!picked.description && <Text style={styles.body} numberOfLines={3}>{picked.description}</Text>}

              <Text style={styles.fieldLabel}>Note to user (optional)</Text>
              <TextInput style={[styles.input, { minHeight: 70 }]} multiline value={note} onChangeText={setNote} placeholder="Why I'm recommending this…" placeholderTextColor={COLORS.textMuted} />

              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
                <Switch value={createCtt} onValueChange={setCreateCtt} />
                <Text style={{ fontSize: 12, color: COLORS.textPrimary }}>Auto-create CTT task on user's account</Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <Switch value={createRoutine} onValueChange={setCreateRoutine} />
                <Text style={{ fontSize: 12, color: COLORS.textPrimary }}>Add as recurring lifestyle routine</Text>
              </View>
              {createRoutine && (
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {(['daily', 'weekdays', 'weekly', 'custom'] as const).map(f => (
                    <TouchableOpacity key={f} onPress={() => setRoutineFreq(f)} style={[styles.chip, routineFreq === f && styles.chipActive]}>
                      <Text style={[styles.chipText, routineFreq === f && styles.chipTextActive]}>{f}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>
          )}

          {picked && (
            <TouchableOpacity testID="xnm-confirm-recommend" onPress={submit} disabled={submitting} style={[styles.btnPrimary, { opacity: submitting ? 0.6 : 1 }]}>
              {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Recommend & {createCtt || createRoutine ? 'create tracker' : 'send'}</Text>}
            </TouchableOpacity>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  headerTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.white, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  solCard: { width: 160, backgroundColor: COLORS.white, padding: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border },
  solName: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  solType: { fontSize: 10, color: COLORS.textMuted, marginTop: 4, textTransform: 'capitalize' },
  solPrice: { fontSize: 11, color: COLORS.primary, fontWeight: '700', marginTop: 4 },
  card: { backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  sectionH: { fontSize: 12, color: COLORS.textMuted, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  body: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  chipActive: { backgroundColor: COLORS.primary + '22', borderColor: COLORS.primary },
  chipText: { fontSize: 11, color: COLORS.textSecondary },
  chipTextActive: { color: COLORS.primary, fontWeight: '700' },
  btnPrimary: { backgroundColor: COLORS.primary, paddingVertical: 12, paddingHorizontal: 14, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  btnPrimaryText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
});
