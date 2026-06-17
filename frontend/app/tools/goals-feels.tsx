/**
 * /tools/goals-feels — EG sub-module.
 *
 * The applied exercise that combines Goal Setter + Tenses & Feels:
 * for each life-area row, capture problem / need / aspiration, the
 * primary emotion associated with it, intensity, and the healing feeling.
 *
 * Top-left arrow → Back to EG hub.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { TENSES_FEELS_LIFE_AREAS, ALL_EMOTIONS, HEALING_FEELINGS } from '../../src/data/tensesFeelsContent';

interface Row {
  area_of_life: string;
  area_label?: string;
  sub_area: string;
  problem: string;
  need: string;
  aspiration: string;
  source_tense: 'past' | 'present' | 'future';
  primary_emotion: string;
  degree: number;
  healing_feeling: string;
}

const seedRows = (): Row[] => {
  const rows: Row[] = [];
  TENSES_FEELS_LIFE_AREAS.forEach((a) => {
    if (a.sub_areas.length === 0) {
      rows.push({ area_of_life: a.code, area_label: a.label, sub_area: '', problem: '', need: '', aspiration: '', source_tense: 'present', primary_emotion: '', degree: 5, healing_feeling: '' });
    } else {
      a.sub_areas.forEach((sa) => {
        rows.push({ area_of_life: a.code, area_label: a.label, sub_area: sa, problem: '', need: '', aspiration: '', source_tense: 'present', primary_emotion: '', degree: 5, healing_feeling: '' });
      });
    }
  });
  return rows;
};

export default function GoalsFeelsScreen() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([]);
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [sheetName, setSheetName] = useState('My Goals & Feels');
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/tenses-feels/goals-feels/latest');
        if (data?.sheet?.rows?.length) {
          setRows(data.sheet.rows.map((r: any) => {
            const meta = TENSES_FEELS_LIFE_AREAS.find(a => a.code === r.area_of_life);
            return { ...r, area_label: meta?.label || r.area_of_life };
          }));
          setSheetId(data.sheet.id);
          setSheetName(data.sheet.sheet_name || 'My Goals & Feels');
        } else {
          setRows(seedRows());
        }
      } catch {
        setRows(seedRows());
      }
    })();
  }, []);

  const updateRow = (idx: number, patch: Partial<Row>) => {
    setRows(rs => rs.map((r, i) => i === idx ? { ...r, ...patch } : r));
  };

  const groupedByArea = rows.reduce<Record<string, Row[]>>((acc, r) => {
    (acc[r.area_of_life] = acc[r.area_of_life] || []).push(r);
    return acc;
  }, {});

  const save = async () => {
    setSaving(true);
    try {
      // Strip UI-only fields
      const cleanRows = rows.map(({ area_label, ...rest }) => rest);
      if (sheetId) {
        await api.put(`/tenses-feels/goals-feels/${sheetId}`, { sheet_name: sheetName, rows: cleanRows });
      } else {
        const { data } = await api.post('/tenses-feels/goals-feels', { sheet_name: sheetName, rows: cleanRows });
        if (data?.sheet?.id) setSheetId(data.sheet.id);
      }
      showAlert('Saved', 'Goals & Feels sheet saved. Review weekly until accomplishment.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally { setSaving(false); }
  };

  const filledCount = rows.filter(r => r.problem || r.need || r.aspiration || r.primary_emotion).length;

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <LinearGradient colors={['#8B5CF6', '#6D28D9']} style={s.header}>
        <TouchableOpacity onPress={() => router.replace('/tools/emotional-gatekeeper' as any)} style={s.backBtn} accessibilityLabel="Back to Emotional Gatekeeper">
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={s.title}>Goals & Feels</Text>
        <Text style={s.subtitle}>Goal Setter × Tenses & Feels — introspect emotions in your goals</Text>
        <View style={s.progressPill}>
          <Ionicons name="checkmark-done" size={12} color="#FFF" />
          <Text style={s.progressText}>{filledCount} / {rows.length} rows filled</Text>
        </View>
      </LinearGradient>

      <ScrollView contentContainerStyle={{ padding: 14 }}>
        <View style={s.howCard}>
          <Text style={s.howH}>How this works</Text>
          <Text style={s.howBody}>For each goal across all 10 areas of life, identify whether it is a resolution for a problem or fulfillment of a need / aspiration. Mark the primary emotion associated, its intensity (1–10), and the healing feeling that should replace it.</Text>
        </View>

        <Text style={s.lbl}>Sheet name</Text>
        <TextInput style={s.inp} value={sheetName} onChangeText={setSheetName} placeholder="My Goals & Feels" placeholderTextColor="#94A3B8" />

        {Object.entries(groupedByArea).map(([code, list]) => {
          const meta = TENSES_FEELS_LIFE_AREAS.find(a => a.code === code);
          const isOpen = expanded[code] !== false;
          return (
            <View key={code} style={s.areaCard}>
              <TouchableOpacity style={s.areaHead} onPress={() => setExpanded(e => ({ ...e, [code]: !isOpen }))}>
                <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={16} color="#FFF" />
                <Text style={s.areaH}>{meta?.label || code}</Text>
                <Text style={s.areaCount}>{list.length} row{list.length === 1 ? '' : 's'}</Text>
              </TouchableOpacity>
              {isOpen && list.map((r) => {
                const idx = rows.indexOf(r);
                return (
                  <View key={`${code}-${idx}`} style={s.rowCard}>
                    {!!r.sub_area && <Text style={s.rowSub}>{r.sub_area}</Text>}
                    <Text style={s.fieldLbl}>Problem</Text>
                    <TextInput style={s.fieldInp} value={r.problem} onChangeText={(v) => updateRow(idx, { problem: v })} placeholder="What is the issue here?" placeholderTextColor="#94A3B8" />
                    <Text style={s.fieldLbl}>Need / Aspiration</Text>
                    <TextInput style={s.fieldInp} value={r.need} onChangeText={(v) => updateRow(idx, { need: v })} placeholder="What do I need / aspire for?" placeholderTextColor="#94A3B8" />
                    <Text style={s.fieldLbl}>Source tense</Text>
                    <View style={s.tenseRow}>
                      {(['past', 'present', 'future'] as const).map(t => (
                        <TouchableOpacity key={t} style={[s.tBtn, r.source_tense === t && s.tBtnOn]} onPress={() => updateRow(idx, { source_tense: t })}>
                          <Text style={[s.tBtnText, r.source_tense === t && { color: '#FFF' }]}>{t}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <Text style={s.fieldLbl}>Primary emotion</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                      {ALL_EMOTIONS.filter(e => e.tense === r.source_tense).map(e => (
                        <TouchableOpacity key={e.code} style={[s.emoChip, r.primary_emotion === e.code && { backgroundColor: e.color, borderColor: e.color }]} onPress={() => updateRow(idx, { primary_emotion: e.code, healing_feeling: e.healing_feeling })}>
                          <Text style={[s.emoChipText, r.primary_emotion === e.code && { color: '#FFF' }]}>{e.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                    <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.fieldLbl}>Degree (1–10)</Text>
                        <TextInput style={s.fieldInp} keyboardType="numeric" value={String(r.degree)} onChangeText={(v) => updateRow(idx, { degree: Math.min(10, Math.max(1, Number(v) || 5)) })} />
                      </View>
                      <View style={{ flex: 2 }}>
                        <Text style={s.fieldLbl}>Healing feeling</Text>
                        <View style={{ flexDirection: 'row', gap: 4 }}>
                          {HEALING_FEELINGS.map(h => (
                            <TouchableOpacity key={h.code} style={[s.healChip, r.healing_feeling === h.code && { backgroundColor: h.color, borderColor: h.color }]} onPress={() => updateRow(idx, { healing_feeling: h.code })}>
                              <Ionicons name={h.icon as any} size={10} color={r.healing_feeling === h.code ? '#FFF' : h.color} />
                            </TouchableOpacity>
                          ))}
                        </View>
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
          );
        })}

        <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="save" size={16} color="#FFF" /><Text style={s.saveBtnText}>  Save Goals & Feels</Text></>)}
        </TouchableOpacity>
        <Text style={s.hint}>✨ Review this sheet weekly until your goals are accomplished.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#FAF5FF' },
  header: { padding: 16, paddingBottom: 20 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 22, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  progressPill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(255,255,255,0.18)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginTop: 8 },
  progressText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  howCard: { backgroundColor: '#F5F3FF', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#DDD6FE' },
  howH: { fontSize: 12, fontWeight: '800', color: '#6D28D9' },
  howBody: { fontSize: 12, color: '#1F2937', marginTop: 4, lineHeight: 18 },
  lbl: { fontSize: 12, fontWeight: '700', color: '#475569', marginTop: 12, marginBottom: 4 },
  inp: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  areaCard: { backgroundColor: '#FFF', borderRadius: 10, marginTop: 12, borderWidth: 1, borderColor: '#E2E8F0', overflow: 'hidden' },
  areaHead: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#6D28D9', padding: 10 },
  areaH: { color: '#FFF', fontSize: 13, fontWeight: '800', flex: 1 },
  areaCount: { color: 'rgba(255,255,255,0.85)', fontSize: 11 },
  rowCard: { padding: 10, borderTopWidth: 1, borderColor: '#F1F5F9' },
  rowSub: { fontSize: 12, fontWeight: '700', color: '#6D28D9', marginBottom: 4 },
  fieldLbl: { fontSize: 10, fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginTop: 6 },
  fieldInp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 6, padding: 8, fontSize: 12, color: '#0F172A', marginTop: 2 },
  tenseRow: { flexDirection: 'row', gap: 4, marginTop: 2 },
  tBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 5, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  tBtnOn: { backgroundColor: '#6D28D9', borderColor: '#6D28D9' },
  tBtnText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  emoChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 5, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', marginRight: 4, marginTop: 4 },
  emoChipText: { fontSize: 10, fontWeight: '700', color: '#475569' },
  healChip: { width: 28, height: 28, borderRadius: 14, borderWidth: 1.5, borderColor: '#CBD5E1', alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#6D28D9', borderRadius: 12, padding: 14, marginTop: 16 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  hint: { fontSize: 11, color: '#6D28D9', textAlign: 'center', marginTop: 8, fontStyle: 'italic' },
});
