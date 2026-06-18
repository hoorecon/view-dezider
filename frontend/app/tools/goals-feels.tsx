/**
 * /tools/goals-feels — EG sub-module.
 *
 * The applied exercise that combines Goal Setter + Tenses & Feels:
 *   For each life-area sub-row, the user picks a Goal Type
 *   (Problem / Need / Risk / Aspiration), autosuggests a goal from
 *   Goal Setter scoped to that life-area + type, then lists multiple
 *   "Associated Emotion(s)" each with its own Healing Feeling (shown
 *   with text labels, not just icons).
 *
 * Top-left arrow → Back to EG hub.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { TENSES_FEELS_LIFE_AREAS, ALL_EMOTIONS, HEALING_FEELINGS } from '../../src/data/tensesFeelsContent';

// 4 Goal Types — must match Goal Setter's goal_type slugs
const GOAL_TYPES = [
  { code: 'problem',    label: 'Problem',    color: '#DC2626', helper: 'What is the issue here?' },
  { code: 'need',       label: 'Need',       color: '#EA580C', helper: 'What is essential / missing?' },
  { code: 'risk',       label: 'Risk',       color: '#7C3AED', helper: 'What might go wrong?' },
  { code: 'aspiration', label: 'Aspiration', color: '#0EA5E9', helper: 'What do I aspire for?' },
] as const;

// 4 ↔ Goal Setter type slug mapping
const GOAL_TYPE_TO_SETTER: Record<string, string> = {
  problem:    'problem_resolution',
  need:       'need_fulfillment',
  risk:       'risk_management',
  aspiration: 'aspiration_achievement',
};

interface AssocEmotion { emotion_code: string; healing_feeling: string; degree: number; }
interface Row {
  area_of_life: string;
  area_label?: string;
  sub_area: string;
  goal_type: '' | 'problem' | 'need' | 'risk' | 'aspiration';
  goal_title: string;
  goal_setter_id?: string | null;
  source_tense: 'past' | 'present' | 'future';
  associated_emotions: AssocEmotion[];
  // Legacy fields preserved for back-compat
  problem?: string; need?: string; aspiration?: string;
  primary_emotion?: string; degree?: number; healing_feeling?: string;
}

const seedRows = (): Row[] => {
  const rows: Row[] = [];
  TENSES_FEELS_LIFE_AREAS.forEach((a) => {
    if (a.sub_areas.length === 0) {
      rows.push({ area_of_life: a.code, area_label: a.label, sub_area: '', goal_type: '', goal_title: '', goal_setter_id: null, source_tense: 'present', associated_emotions: [] });
    } else {
      a.sub_areas.forEach((sa) => {
        rows.push({ area_of_life: a.code, area_label: a.label, sub_area: sa, goal_type: '', goal_title: '', goal_setter_id: null, source_tense: 'present', associated_emotions: [] });
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
  const [smartGoals, setSmartGoals] = useState<any[]>([]);
  const [focusedIdx, setFocusedIdx] = useState<number | null>(null);

  // Load existing sheet + Goal Setter pool
  useEffect(() => {
    (async () => {
      try {
        const [sheet, gs] = await Promise.all([
          api.get('/tenses-feels/goals-feels/latest'),
          api.get('/goal-setter/goals'),
        ]);
        if (sheet.data?.sheet?.rows?.length) {
          setRows(sheet.data.sheet.rows.map((r: any) => {
            const meta = TENSES_FEELS_LIFE_AREAS.find(a => a.code === r.area_of_life);
            // Back-fill legacy rows so they render in the new UI
            const back: Row = {
              area_of_life: r.area_of_life,
              area_label: meta?.label || r.area_of_life,
              sub_area: r.sub_area || '',
              goal_type: r.goal_type || (r.problem ? 'problem' : r.need ? 'need' : r.aspiration ? 'aspiration' : ''),
              goal_title: r.goal_title || r.problem || r.need || r.aspiration || '',
              goal_setter_id: r.goal_setter_id || null,
              source_tense: r.source_tense || 'present',
              associated_emotions: Array.isArray(r.associated_emotions) && r.associated_emotions.length
                ? r.associated_emotions
                : (r.primary_emotion ? [{ emotion_code: r.primary_emotion, healing_feeling: r.healing_feeling || '', degree: r.degree || 5 }] : []),
              problem: r.problem, need: r.need, aspiration: r.aspiration,
            };
            return back;
          }));
          setSheetId(sheet.data.sheet.id);
          setSheetName(sheet.data.sheet.sheet_name || 'My Goals & Feels');
        } else {
          setRows(seedRows());
        }
        setSmartGoals(gs.data || []);
      } catch {
        setRows(seedRows());
      }
    })();
  }, []);

  const updateRow = (idx: number, patch: Partial<Row>) => {
    setRows(rs => rs.map((r, i) => i === idx ? { ...r, ...patch } : r));
  };

  // Suggestion pool for a row's (life_area, goal_type)
  const getSuggestions = (r: Row): any[] => {
    if (!r.goal_type) return [];
    const setterType = GOAL_TYPE_TO_SETTER[r.goal_type];
    const q = (r.goal_title || '').trim().toLowerCase();
    return smartGoals
      .filter(g => g.life_area === r.area_of_life || !g.life_area)
      .filter(g => !g.goal_type || g.goal_type === setterType)
      .filter(g => !q || (g.title || '').toLowerCase().includes(q))
      .slice(0, 6);
  };

  // Associated-emotion helpers
  const addEmotion = (idx: number, emotionCode: string) => {
    const e = ALL_EMOTIONS.find(x => x.code === emotionCode);
    if (!e) return;
    const r = rows[idx];
    if (r.associated_emotions.find(x => x.emotion_code === emotionCode)) return;  // dedup
    updateRow(idx, { associated_emotions: [...r.associated_emotions, { emotion_code: emotionCode, healing_feeling: e.healing_feeling, degree: 5 }] });
  };
  const removeEmotion = (idx: number, emotionCode: string) => {
    const r = rows[idx];
    updateRow(idx, { associated_emotions: r.associated_emotions.filter(x => x.emotion_code !== emotionCode) });
  };
  const updateEmotion = (idx: number, emotionCode: string, patch: Partial<AssocEmotion>) => {
    const r = rows[idx];
    updateRow(idx, { associated_emotions: r.associated_emotions.map(x => x.emotion_code === emotionCode ? { ...x, ...patch } : x) });
  };

  const groupedByArea = useMemo(() => rows.reduce<Record<string, Row[]>>((acc, r) => {
    (acc[r.area_of_life] = acc[r.area_of_life] || []).push(r);
    return acc;
  }, {}), [rows]);

  const save = async () => {
    setSaving(true);
    try {
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

  const filledCount = rows.filter(r => r.goal_title || r.associated_emotions.length).length;

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <LinearGradient colors={['#8B5CF6', '#6D28D9']} style={s.header}>
        <TouchableOpacity onPress={() => router.replace('/tools/emotional-gatekeeper' as any)} style={s.backBtn} accessibilityLabel="Back to Emotional Gatekeeper">
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={s.title}>Goals & Feels</Text>
        <Text style={s.subtitle}>Goal Setter × Tenses & Feels — introspect emotions behind your goals</Text>
        <View style={s.progressPill}>
          <Ionicons name="checkmark-done" size={12} color="#FFF" />
          <Text style={s.progressText}>{filledCount} / {rows.length} rows filled</Text>
        </View>
      </LinearGradient>

      <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }} keyboardShouldPersistTaps="handled">
        <View style={s.howCard}>
          <Text style={s.howH}>How this works</Text>
          <Text style={s.howBody}>For each life area, pick a goal type (Problem / Need / Risk / Aspiration) and either type a new goal or select one already created in Goal Setter. Then list every emotion you feel about it — assign a Healing Feeling to each.</Text>
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
                const suggestions = focusedIdx === idx ? getSuggestions(r) : [];
                return (
                  <View key={`${code}-${idx}`} style={s.rowCard}>
                    {!!r.sub_area && <Text style={s.rowSub}>{r.sub_area}</Text>}

                    {/* Goal type radio */}
                    <Text style={s.fieldLbl}>Goal type</Text>
                    <View style={s.typeRow}>
                      {GOAL_TYPES.map(t => {
                        const on = r.goal_type === t.code;
                        return (
                          <TouchableOpacity key={t.code} style={[s.typeBtn, on && { backgroundColor: t.color, borderColor: t.color }]} onPress={() => updateRow(idx, { goal_type: on ? '' : t.code, goal_title: '', goal_setter_id: null })}>
                            <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={12} color={on ? '#FFF' : t.color} />
                            <Text style={[s.typeText, on && { color: '#FFF' }]}>{t.label}</Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>

                    {/* Goal title autosuggest */}
                    {!!r.goal_type && (
                      <>
                        <Text style={s.fieldLbl}>Goal title — {GOAL_TYPES.find(t => t.code === r.goal_type)?.helper || ''}</Text>
                        <TextInput
                          style={s.fieldInp}
                          value={r.goal_title}
                          onChangeText={(v) => updateRow(idx, { goal_title: v, goal_setter_id: null })}
                          onFocus={() => setFocusedIdx(idx)}
                          onBlur={() => setTimeout(() => setFocusedIdx((f) => f === idx ? null : f), 200)}
                          placeholder="Type to search Goal Setter goals…"
                          placeholderTextColor="#94A3B8"
                        />
                        {suggestions.length > 0 && (
                          <View style={s.suggestBox}>
                            {suggestions.map(g => (
                              <TouchableOpacity key={g.goal_id} style={s.suggestRow} onPress={() => { updateRow(idx, { goal_title: g.title, goal_setter_id: g.goal_id }); setFocusedIdx(null); }}>
                                <Ionicons name="flag" size={12} color="#6D28D9" />
                                <Text style={s.suggestTxt} numberOfLines={1}>{g.title}</Text>
                              </TouchableOpacity>
                            ))}
                          </View>
                        )}
                        {r.goal_setter_id && (
                          <View style={s.linkedPill}>
                            <Ionicons name="link" size={10} color="#FFF" />
                            <Text style={s.linkedTxt}>Linked to Goal Setter</Text>
                          </View>
                        )}
                      </>
                    )}

                    {/* Source tense */}
                    <Text style={s.fieldLbl}>Source tense</Text>
                    <View style={s.tenseRow}>
                      {(['past', 'present', 'future'] as const).map(t => (
                        <TouchableOpacity key={t} style={[s.tBtn, r.source_tense === t && s.tBtnOn]} onPress={() => updateRow(idx, { source_tense: t })}>
                          <Text style={[s.tBtnText, r.source_tense === t && { color: '#FFF' }]}>{t}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>

                    {/* Add associated emotions */}
                    <Text style={s.fieldLbl}>Associated emotion(s) — tap to add</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                      {ALL_EMOTIONS.filter(e => e.tense === r.source_tense).map(e => {
                        const picked = r.associated_emotions.find(x => x.emotion_code === e.code);
                        return (
                          <TouchableOpacity key={e.code} style={[s.emoChip, picked && { backgroundColor: e.color, borderColor: e.color }]} onPress={() => picked ? removeEmotion(idx, e.code) : addEmotion(idx, e.code)}>
                            {picked && <Ionicons name="checkmark" size={10} color="#FFF" />}
                            <Text style={[s.emoChipText, picked && { color: '#FFF' }]}>{e.label}</Text>
                          </TouchableOpacity>
                        );
                      })}
                    </ScrollView>

                    {/* Per-emotion: degree + healing feeling (with text) */}
                    {r.associated_emotions.length > 0 && (
                      <View style={s.assocBlock}>
                        {r.associated_emotions.map(ae => {
                          const e = ALL_EMOTIONS.find(x => x.code === ae.emotion_code);
                          return (
                            <View key={ae.emotion_code} style={[s.assocCard, { borderLeftColor: e?.color || '#8B5CF6' }]}>
                              <View style={s.assocHead}>
                                <Text style={s.assocLabel}>{e?.label || ae.emotion_code}</Text>
                                <TouchableOpacity onPress={() => removeEmotion(idx, ae.emotion_code)}>
                                  <Ionicons name="close-circle" size={16} color="#94A3B8" />
                                </TouchableOpacity>
                              </View>
                              <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', marginTop: 4 }}>
                                <Text style={s.miniLbl}>Degree</Text>
                                <TextInput style={s.degInp} keyboardType="numeric" value={String(ae.degree)} onChangeText={(v) => updateEmotion(idx, ae.emotion_code, { degree: Math.min(10, Math.max(1, Number(v) || 5)) })} />
                                <Text style={s.miniLbl}>/10</Text>
                              </View>
                              <Text style={s.miniLbl}>Healing feeling to replace it with</Text>
                              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                                {HEALING_FEELINGS.map(h => {
                                  const on = ae.healing_feeling === h.code;
                                  return (
                                    <TouchableOpacity key={h.code} style={[s.healPill, on && { backgroundColor: h.color, borderColor: h.color }]} onPress={() => updateEmotion(idx, ae.emotion_code, { healing_feeling: h.code })}>
                                      <Ionicons name={h.icon as any} size={12} color={on ? '#FFF' : h.color} />
                                      <Text style={[s.healPillText, on && { color: '#FFF' }]}>{h.label}</Text>
                                    </TouchableOpacity>
                                  );
                                })}
                              </View>
                            </View>
                          );
                        })}
                      </View>
                    )}
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
  typeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  typeBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFF' },
  typeText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  suggestBox: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 6, marginTop: 4, overflow: 'hidden' },
  suggestRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 8, borderBottomWidth: 1, borderColor: '#F1F5F9' },
  suggestTxt: { fontSize: 12, color: '#0F172A', flex: 1 },
  linkedPill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#10B981', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginTop: 4 },
  linkedTxt: { color: '#FFF', fontSize: 10, fontWeight: '700' },
  tenseRow: { flexDirection: 'row', gap: 4, marginTop: 2 },
  tBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 5, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  tBtnOn: { backgroundColor: '#6D28D9', borderColor: '#6D28D9' },
  tBtnText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  emoChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 5, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', marginRight: 4, marginTop: 4 },
  emoChipText: { fontSize: 10, fontWeight: '700', color: '#475569' },
  assocBlock: { marginTop: 10 },
  assocCard: { backgroundColor: '#FAF5FF', borderRadius: 8, padding: 8, marginTop: 6, borderLeftWidth: 3 },
  assocHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  assocLabel: { fontSize: 12, fontWeight: '800', color: '#1F2937' },
  miniLbl: { fontSize: 10, color: '#64748B', fontWeight: '700', textTransform: 'uppercase', marginTop: 6 },
  degInp: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 5, paddingHorizontal: 8, paddingVertical: 4, width: 46, fontSize: 12, textAlign: 'center' },
  healPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFF', marginTop: 4 },
  healPillText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#6D28D9', borderRadius: 12, padding: 14, marginTop: 16 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  hint: { fontSize: 11, color: '#6D28D9', textAlign: 'center', marginTop: 8, fontStyle: 'italic' },
});
