import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
  Linking, RefreshControl,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import api from '../../src/utils/api';

interface Stage { stage_number: number; letter: string; name: string; color: string; icon: string; summary: string; steps: any[]; audio_url?: string; audio_title?: string; }

export default function GoalManifestationScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<'list' | 'journey'>('list');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [stages, setStages] = useState<Stage[]>([]);
  const [journeys, setJourneys] = useState<any[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);

  // Journey state
  const [wish, setWish] = useState('');
  const [currentStage, setCurrentStage] = useState(1);
  const [stageInputs, setStageInputs] = useState<Record<string, string>>({});
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [editId, setEditId] = useState('');
  const [meditationPrefs, setMeditationPrefs] = useState<Record<string, any>>({});

  const fetchData = async () => {
    try {
      const [fwRes, jRes, dRes, medRes] = await Promise.all([
        api.get('/goal-manifestation/framework'),
        api.get('/goal-manifestation/journeys'),
        api.get('/goal-manifestation/dashboard'),
        api.get('/meditation-settings/preferences').catch(() => ({ data: { meditations: {} } })),
      ]);
      setStages(fwRes.data?.stages || []);
      setJourneys(jRes.data || []);
      setDashboard(dRes.data);
      setMeditationPrefs(medRes.data?.meditations || {});
    } catch (e) { console.error('Manifestation fetch:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const startNew = () => {
    setWish(''); setCurrentStage(1); setStageInputs({}); setExpandedSteps({}); setEditId('');
    setMode('journey');
  };

  const openJourney = (j: any) => {
    setWish(j.wish || ''); setCurrentStage(j.current_stage || 1);
    setStageInputs(j.stage_inputs || {}); setEditId(j.journey_id); setExpandedSteps({});
    setMode('journey');
  };

  const toggleStep = (stepId: string) => {
    setExpandedSteps(prev => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const updateInput = (stepId: string, value: string) => {
    setStageInputs(prev => ({ ...prev, [stepId]: value }));
  };

  const handleSave = async () => {
    if (!wish.trim()) { showAlert('Required', 'Enter your wish / goal'); return; }
    setSaving(true);
    try {
      const payload = { wish: wish.trim(), current_stage: currentStage, stage_inputs: stageInputs };
      if (editId) {
        await api.put(`/goal-manifestation/journeys/${editId}`, payload);
      } else {
        await api.post('/goal-manifestation/journeys', payload);
      }
      showAlert('Saved', 'Manifestation journey saved!');
      setMode('list'); fetchData();
    } catch (e) { showAlert('Error', 'Failed to save'); }
    finally { setSaving(false); }
  };

  const handleDelete = (id: string) => {
    showAlert('Delete', 'Remove this journey?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/goal-manifestation/journeys/${id}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed'); }
      }},
    ]);
  };

  const activeStage = stages.find(s => s.stage_number === currentStage);

  // Resolve meditation URLs from user prefs
  const resolveStepLink = (step: any): string => {
    if (step.id === '1.1' && meditationPrefs.guru_invocation?.resolved_url) {
      return meditationPrefs.guru_invocation.resolved_url;
    }
    if (step.id === '1.6' && meditationPrefs.stillness_meditation?.resolved_url) {
      return meditationPrefs.stillness_meditation.resolved_url;
    }
    if (step.id === '4.4' && meditationPrefs.guru_invocation?.resolved_url) {
      return meditationPrefs.guru_invocation.resolved_url;
    }
    return step.link || '';
  };

  const resolveStageAudio = (stage: Stage): string => {
    if (stage.stage_number === 4 && meditationPrefs.goal_manifestation?.resolved_url) {
      return meditationPrefs.goal_manifestation.resolved_url;
    }
    return stage.audio_url || '';
  };

  const renderList = () => (
    <>
      {dashboard && (
        <View style={st.statsRow}>
          <View style={st.statBox}><Text style={st.statNum}>{dashboard.total_journeys}</Text><Text style={st.statLabel}>Journeys</Text></View>
          <View style={st.statBox}><Text style={st.statNum}>{dashboard.active}</Text><Text style={st.statLabel}>Active</Text></View>
          <View style={st.statBox}><Text style={st.statNum}>{dashboard.manifested}</Text><Text style={st.statLabel}>Manifested</Text></View>
        </View>
      )}

      {/* Stage overview */}
      <Text style={st.sectionTitle}>CAB-FAME — 7 Stages</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {stages.map(s => (
            <View key={s.stage_number} style={[st.stagePill, { borderColor: s.color }]}>
              <Text style={[st.stageLetterSmall, { color: s.color }]}>{s.letter}</Text>
              <Text style={st.stageNameSmall} numberOfLines={1}>{s.name}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {journeys.length === 0 ? (
        <View style={st.empty}>
          <View style={st.emptyIcon}><Ionicons name="sparkles-outline" size={48} color={COLORS.textMuted} /></View>
          <Text style={st.emptyTitle}>Begin Your Manifestation</Text>
          <Text style={st.emptySub}>Use the ancient 7-stage CAB-FAME process to manifest your deepest wishes</Text>
        </View>
      ) : (
        journeys.map(j => (
          <TouchableOpacity key={j.journey_id} style={st.journeyCard} onPress={() => openJourney(j)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={st.journeyWish} numberOfLines={2}>{j.wish}</Text>
                <Text style={st.journeySub}>Stage {j.current_stage}/7 · {j.status} · {j.created_at?.split('T')[0]}</Text>
              </View>
              <TouchableOpacity onPress={() => handleDelete(j.journey_id)}>
                <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            {/* Progress dots */}
            <View style={st.progressDots}>
              {stages.map(s => (
                <View key={s.stage_number} style={[st.pDot, {
                  backgroundColor: s.stage_number <= (j.current_stage || 1) ? s.color : COLORS.divider,
                }]}>
                  <Text style={[st.pDotLetter, { color: s.stage_number <= (j.current_stage || 1) ? '#FFF' : COLORS.textMuted }]}>{s.letter}</Text>
                </View>
              ))}
            </View>
          </TouchableOpacity>
        ))
      )}
    </>
  );

  const renderJourney = () => (
    <>
      {/* Wish input */}
      <Text style={st.formLabel}>My Wish / Goal *</Text>
      <TextInput style={st.wishInput} value={wish} onChangeText={setWish}
        placeholder="What do you wish to manifest?" placeholderTextColor={COLORS.textMuted} multiline />

      {/* Stage tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginVertical: 12 }}>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          {stages.map(s => (
            <TouchableOpacity key={s.stage_number}
              style={[st.stageTab, currentStage === s.stage_number && { backgroundColor: s.color, borderColor: s.color }]}
              onPress={() => setCurrentStage(s.stage_number)}>
              <Text style={[st.stageTabText, currentStage === s.stage_number && { color: '#FFF' }]}>
                {s.stage_number}. {s.letter}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Active stage content */}
      {activeStage && (
        <View style={[st.stageCard, { borderLeftColor: activeStage.color }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <View style={[st.stageIcon, { backgroundColor: activeStage.color }]}>
              <Ionicons name={activeStage.icon as any} size={20} color="#FFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={st.stageName}>{activeStage.stage_number}. {activeStage.letter} — {activeStage.name}</Text>
              <Text style={st.stageSummary}>{activeStage.summary}</Text>
            </View>
          </View>

          {/* Audio player if stage has one */}
          {(activeStage.audio_url || (activeStage.stage_number === 4 && meditationPrefs.goal_manifestation)) && (
            <View style={{ marginBottom: 10 }}>
              <AudioGuidePlayer uri={resolveStageAudio(activeStage)} title={activeStage.audio_title || 'Meditation'} color={activeStage.color} />
            </View>
          )}

          {/* Steps */}
          {activeStage.steps.map((step: any) => {
            const resolvedLink = resolveStepLink(step);
            return (
            <View key={step.id} style={st.stepItem}>
              <TouchableOpacity style={st.stepHeader} onPress={() => toggleStep(step.id)}>
                <Text style={st.stepId}>{step.id}</Text>
                <Text style={st.stepTitle} numberOfLines={expandedSteps[step.id] ? undefined : 1}>{step.title}</Text>
                <Ionicons name={expandedSteps[step.id] ? 'chevron-up' : 'chevron-down'} size={16} color={COLORS.textMuted} />
              </TouchableOpacity>

              {expandedSteps[step.id] && (
                <View style={st.stepBody}>
                  {step.instruction && <Text style={st.stepInstruction}>{step.instruction}</Text>}
                  {step.content && <Text style={st.stepContent}>{step.content}</Text>}
                  {step.followup && <Text style={st.stepFollowup}>{step.followup}</Text>}

                  {/* YouTube / external links — uses resolved URL from user prefs */}
                  {resolvedLink ? (
                    <TouchableOpacity style={st.linkBtn} onPress={() => Linking.openURL(resolvedLink)}>
                      <Ionicons name={resolvedLink.includes('youtube') ? 'logo-youtube' : 'link'} size={16} color="#EF4444" />
                      <Text style={st.linkText}>{step.link_label || 'Open Link'}</Text>
                      {meditationPrefs[step.id === '1.1' || step.id === '4.4' ? 'guru_invocation' : 'stillness_meditation']?.source_type !== 'default' && (
                        <Text style={st.customBadge}>CUSTOM</Text>
                      )}
                    </TouchableOpacity>
                  ) : null}

                  {/* User input field */}
                  {step.has_input && (
                    <TextInput style={st.stepInput}
                      value={stageInputs[step.id] || ''}
                      onChangeText={v => updateInput(step.id, v)}
                      placeholder={step.input_label || 'Your input...'}
                      placeholderTextColor={COLORS.textMuted} multiline />
                  )}
                </View>
              )}
            </View>
          )})}

          {/* Stage navigation */}
          <View style={st.stageNav}>
            {currentStage > 1 && (
              <TouchableOpacity style={st.stageNavBtn} onPress={() => setCurrentStage(currentStage - 1)}>
                <Ionicons name="arrow-back" size={16} color="#7C3AED" />
                <Text style={st.stageNavText}>Previous</Text>
              </TouchableOpacity>
            )}
            <View style={{ flex: 1 }} />
            {currentStage < 7 && (
              <TouchableOpacity style={[st.stageNavBtn, { backgroundColor: '#7C3AED' }]}
                onPress={() => setCurrentStage(currentStage + 1)}>
                <Text style={[st.stageNavText, { color: '#FFF' }]}>Next Stage</Text>
                <Ionicons name="arrow-forward" size={16} color="#FFF" />
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}
    </>
  );

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#7C3AED', '#9333EA']} style={st.header}>
          <TouchableOpacity onPress={() => mode === 'journey' ? setMode('list') : router.back()} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={st.headerTitle}>Goal Manifestation</Text>
            <Text style={st.headerSub}>CAB-FAME · 7-Stage Wish Fulfillment</Text>
          </View>
          {mode === 'list' && (
            <TouchableOpacity onPress={startNew} style={st.addBtn}>
              <Ionicons name="add" size={22} color="#FFF" />
            </TouchableOpacity>
          )}
        </LinearGradient>

        {loading ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}><ActivityIndicator size="large" color="#7C3AED" /></View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
            refreshControl={mode === 'list' ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined}>
            {mode === 'list' ? renderList() : renderJourney()}
          </ScrollView>
        )}

        {mode === 'journey' && (
          <View style={st.bottom}>
            <TouchableOpacity style={[st.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <><Ionicons name="checkmark-circle" size={18} color="#FFF" /><Text style={st.saveBtnText}>Save Journey</Text></>
              )}
            </TouchableOpacity>
          </View>
        )}

        {mode === 'list' && journeys.length > 0 && (
          <View style={st.bottom}>
            <TouchableOpacity style={st.saveBtn} onPress={startNew}>
              <Ionicons name="add-circle" size={18} color="#FFF" /><Text style={st.saveBtnText}>New Journey</Text>
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  addBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },

  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 16, fontWeight: '700', color: '#7C3AED' },
  statLabel: { fontSize: 9, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },

  stagePill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, borderWidth: 1.5, backgroundColor: COLORS.white },
  stageLetterSmall: { fontSize: 13, fontWeight: '800' },
  stageNameSmall: { fontSize: 10, fontWeight: '500', color: COLORS.textMuted, maxWidth: 90 },

  journeyCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  journeyWish: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  journeySub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  progressDots: { flexDirection: 'row', gap: 6, marginTop: 10 },
  pDot: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  pDotLetter: { fontSize: 11, fontWeight: '700' },

  formLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  wishInput: { backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: COLORS.textPrimary, minHeight: 60, textAlignVertical: 'top' },

  stageTab: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  stageTabText: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },

  stageCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, borderLeftWidth: 4, borderWidth: 1, borderColor: COLORS.border },
  stageIcon: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  stageName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  stageSummary: { fontSize: 12, color: COLORS.textMuted, marginTop: 1 },

  stepItem: { marginTop: 10, borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 8 },
  stepHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  stepId: { fontSize: 11, fontWeight: '700', color: '#7C3AED', width: 24 },
  stepTitle: { flex: 1, fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  stepBody: { paddingLeft: 30, paddingTop: 6 },
  stepInstruction: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 4, fontStyle: 'italic' },
  stepContent: { fontSize: 13, color: COLORS.textPrimary, lineHeight: 20, marginBottom: 4, backgroundColor: '#F8FAFC', padding: 10, borderRadius: 8 },
  stepFollowup: { fontSize: 12, color: '#EF4444', fontWeight: '600', marginBottom: 4 },

  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 12, backgroundColor: '#FEF2F2', borderRadius: 10, marginTop: 4, alignSelf: 'flex-start' },
  linkText: { fontSize: 12, fontWeight: '600', color: '#EF4444' },
  customBadge: { fontSize: 8, fontWeight: '700', color: '#10B981', backgroundColor: '#10B98118', paddingHorizontal: 4, paddingVertical: 1, borderRadius: 4, marginLeft: 4 },

  stepInput: { backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1, borderColor: '#7C3AED30', paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary, marginTop: 6, minHeight: 44, textAlignVertical: 'top' },

  stageNav: { flexDirection: 'row', alignItems: 'center', marginTop: 16 },
  stageNavBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: '#7C3AED', backgroundColor: COLORS.white },
  stageNavText: { fontSize: 13, fontWeight: '600', color: '#7C3AED' },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
});
