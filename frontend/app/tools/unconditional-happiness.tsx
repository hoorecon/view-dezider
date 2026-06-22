import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
  RefreshControl,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const JOY_AUDIO = 'https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/zcy23t73_Joy.mp3';

interface Phase { phase_number: number; name: string; icon: string; color: string; prompt: string; instruction: string; reflection_question: string; }

const HAPPINESS_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export default function UnconditionalHappinessScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<'dashboard' | 'practice'>('dashboard');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState<any>(null);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [audioTitle, setAudioTitle] = useState('');

  // Practice state
  const [currentPhase, setCurrentPhase] = useState(1);
  const [reflections, setReflections] = useState<Record<string, string>>({});
  const [happinessBefore, setHappinessBefore] = useState(5);
  const [happinessAfter, setHappinessAfter] = useState(5);
  const [listenedAudio, setListenedAudio] = useState(false);
  const [notes, setNotes] = useState('');

  const fetchData = async () => {
    try {
      const [fwRes, dashRes] = await Promise.all([
        api.get('/unconditional-happiness/framework'),
        api.get('/unconditional-happiness/dashboard'),
      ]);
      setPhases(fwRes.data?.phases || []);
      setAudioTitle(fwRes.data?.audio_title || '');
      setDashboard(dashRes.data);
    } catch (e) { console.error('UH fetch:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const startPractice = () => {
    setCurrentPhase(1); setReflections({}); setHappinessBefore(5);
    setHappinessAfter(5); setListenedAudio(false); setNotes('');
    setMode('practice');
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post('/unconditional-happiness/sessions', {
        reflections, listened_audio: listenedAudio,
        happiness_before: happinessBefore, happiness_after: happinessAfter, notes,
      });
      showAlert('Wonderful!', 'Your happiness practice has been logged. Keep celebrating!');
      setMode('dashboard'); fetchData();
    } catch (e) { showAlert('Error', 'Failed to save'); }
    finally { setSaving(false); }
  };

  const activePhase = phases.find(p => p.phase_number === currentPhase);

  const renderDashboard = () => (
    <>
      {/* Stats */}
      {dashboard && (
        <View style={s.statsRow}>
          <View style={s.statBox}>
            <Text style={s.statNum}>{dashboard.total_sessions || 0}</Text>
            <Text style={s.statLabel}>Sessions</Text>
          </View>
          <View style={s.statBox}>
            <Text style={[s.statNum, { color: '#F59E0B' }]}>{dashboard.current_streak || 0}</Text>
            <Text style={s.statLabel}>Streak</Text>
          </View>
          <View style={s.statBox}>
            <Text style={[s.statNum, { color: '#10B981' }]}>{dashboard.best_streak || 0}</Text>
            <Text style={s.statLabel}>Best Streak</Text>
          </View>
          <View style={s.statBox}>
            <Text style={[s.statNum, { color: '#3B82F6' }]}>+{dashboard.avg_happiness_improvement || 0}</Text>
            <Text style={s.statLabel}>Avg Uplift</Text>
          </View>
        </View>
      )}

      {/* Quote */}
      <View style={s.quoteCard}>
        <Text style={s.quoteText}>
          "Let us NOT attach any conditions or reasons to be happy. Let us celebrate the life of unconditional happiness from now on!"
        </Text>
      </View>

      {/* Audio */}
      <View style={s.audioCard}>
        <AudioGuidePlayer uri={JOY_AUDIO} title={audioTitle || 'Joy — Unconditional Happiness'} color="#EC4899" />
      </View>

      {/* Phases overview */}
      <Text style={s.sectionTitle}>The 4 Phases</Text>
      {phases.map(p => (
        <View key={p.phase_number} style={s.phaseOverview}>
          <View style={[s.phaseIcon, { backgroundColor: p.color }]}>
            <Ionicons name={p.icon as any} size={16} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.phaseNameSmall}>{p.phase_number}. {p.name}</Text>
            <Text style={s.phasePromptSmall} numberOfLines={2}>{p.prompt}</Text>
          </View>
        </View>
      ))}

      {/* Recent sessions */}
      {dashboard?.recent_sessions?.length > 0 && (
        <>
          <Text style={[s.sectionTitle, { marginTop: 16 }]}>Recent Sessions</Text>
          {dashboard.recent_sessions.map((sess: any, i: number) => (
            <View key={i} style={s.sessCard}>
              <Text style={s.sessDate}>{sess.created_at?.split('T')[0]}</Text>
              <Text style={s.sessChange}>
                Happiness: {sess.happiness_before} → {sess.happiness_after}
                {sess.happiness_after > sess.happiness_before ? ' ↑' : ''}
              </Text>
            </View>
          ))}
        </>
      )}
    </>
  );

  const renderPractice = () => (
    <>
      {/* Before rating */}
      {currentPhase === 1 && (
        <View style={s.ratingCard}>
          <Text style={s.ratingTitle}>Before we begin — How happy do you feel right now?</Text>
          <View style={s.ratingRow}>
            {HAPPINESS_LEVELS.map(l => (
              <TouchableOpacity key={l}
                style={[s.ratingDot, happinessBefore === l && { backgroundColor: '#EC4899', borderColor: '#EC4899' }]}
                onPress={() => setHappinessBefore(l)}>
                <Text style={[s.ratingText, happinessBefore === l && { color: '#FFF' }]}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Phase content */}
      {activePhase && (
        <View style={[s.phaseCard, { borderLeftColor: activePhase.color }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <View style={[s.phaseIconBig, { backgroundColor: activePhase.color }]}>
              <Ionicons name={activePhase.icon as any} size={22} color="#FFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.phaseName}>Phase {activePhase.phase_number}: {activePhase.name}</Text>
            </View>
          </View>

          <View style={s.promptBox}>
            <Text style={s.promptText}>{activePhase.prompt}</Text>
          </View>

          <Text style={s.instructionText}>{activePhase.instruction}</Text>

          {/* Phase 3: Audio integration */}
          {activePhase.phase_number === 3 && (
            <View style={{ marginVertical: 10 }}>
              <AudioGuidePlayer uri={JOY_AUDIO} title="Play: Joy — Celebrate!" color="#EC4899" />
              <TouchableOpacity style={s.audioToggle} onPress={() => setListenedAudio(!listenedAudio)}>
                <Ionicons name={listenedAudio ? 'checkbox' : 'square-outline'} size={20} color="#EC4899" />
                <Text style={s.audioToggleText}>I listened to the audio & celebrated!</Text>
              </TouchableOpacity>
            </View>
          )}

          <Text style={s.reflectionLabel}>Reflection: {activePhase.reflection_question}</Text>
          <TextInput style={s.reflectionInput}
            value={reflections[String(activePhase.phase_number)] || ''}
            onChangeText={v => setReflections(prev => ({ ...prev, [String(activePhase.phase_number)]: v }))}
            placeholder="Your reflection..." placeholderTextColor={COLORS.textMuted} multiline />

          {/* Navigation */}
          <View style={s.phaseNav}>
            {currentPhase > 1 && (
              <TouchableOpacity style={s.navBtn} onPress={() => setCurrentPhase(currentPhase - 1)}>
                <Ionicons name="arrow-back" size={16} color="#EC4899" /><Text style={s.navBtnText}>Prev</Text>
              </TouchableOpacity>
            )}
            <View style={{ flex: 1 }} />
            {currentPhase < 4 ? (
              <TouchableOpacity style={[s.navBtn, { backgroundColor: '#EC4899' }]}
                onPress={() => setCurrentPhase(currentPhase + 1)}>
                <Text style={[s.navBtnText, { color: '#FFF' }]}>Next Phase</Text>
                <Ionicons name="arrow-forward" size={16} color="#FFF" />
              </TouchableOpacity>
            ) : (
              /* After rating + complete */
              <View />
            )}
          </View>
        </View>
      )}

      {/* After rating (phase 4) */}
      {currentPhase === 4 && (
        <View style={s.ratingCard}>
          <Text style={s.ratingTitle}>After the practice — How happy do you feel now?</Text>
          <View style={s.ratingRow}>
            {HAPPINESS_LEVELS.map(l => (
              <TouchableOpacity key={l}
                style={[s.ratingDot, happinessAfter === l && { backgroundColor: '#10B981', borderColor: '#10B981' }]}
                onPress={() => setHappinessAfter(l)}>
                <Text style={[s.ratingText, happinessAfter === l && { color: '#FFF' }]}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>
          {happinessAfter > happinessBefore && (
            <Text style={s.upliftText}>+{happinessAfter - happinessBefore} happiness uplift!</Text>
          )}
        </View>
      )}

      {/* Notes */}
      <Text style={s.formLabel}>Additional Notes</Text>
      <TextInput style={s.notesInput} value={notes} onChangeText={setNotes}
        placeholder="Any thoughts..." placeholderTextColor={COLORS.textMuted} multiline />
    </>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#EC4899', '#F472B6']} style={s.header}>
          <TouchableOpacity onPress={() => mode === 'practice' ? setMode('dashboard') : safeBack(router)} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>Unconditional Happiness</Text>
            <Text style={s.headerSub}>Celebrate life without conditions</Text>
          </View>
        </LinearGradient>

        {loading ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}><ActivityIndicator size="large" color="#EC4899" /></View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
            refreshControl={mode === 'dashboard' ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined}>
            {mode === 'dashboard' ? renderDashboard() : renderPractice()}
          </ScrollView>
        )}

        <View style={s.bottom}>
          {mode === 'dashboard' ? (
            <TouchableOpacity style={s.saveBtn} onPress={startPractice}>
              <Ionicons name="happy" size={18} color="#FFF" />
              <Text style={s.saveBtnText}>Start Happiness Practice</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <><Ionicons name="checkmark-circle" size={18} color="#FFF" /><Text style={s.saveBtnText}>Complete & Save</Text></>
              )}
            </TouchableOpacity>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  statsRow: { flexDirection: 'row', gap: 6, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 16, fontWeight: '700', color: '#EC4899' },
  statLabel: { fontSize: 8, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  quoteCard: { backgroundColor: '#FDF2F8', borderRadius: 14, padding: 16, marginBottom: 12, borderLeftWidth: 4, borderLeftColor: '#EC4899' },
  quoteText: { fontSize: 14, color: '#831843', lineHeight: 22, fontStyle: 'italic' },

  audioCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },

  phaseOverview: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  phaseIcon: { width: 32, height: 32, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  phaseNameSmall: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  phasePromptSmall: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },

  sessCard: { backgroundColor: COLORS.white, borderRadius: 10, padding: 10, marginBottom: 6, flexDirection: 'row', justifyContent: 'space-between', borderWidth: 1, borderColor: COLORS.border },
  sessDate: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  sessChange: { fontSize: 12, color: '#10B981', fontWeight: '600' },

  ratingCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  ratingTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 10 },
  ratingRow: { flexDirection: 'row', gap: 4, flexWrap: 'wrap', justifyContent: 'center' },
  ratingDot: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center', borderWidth: 2, borderColor: COLORS.border },
  ratingText: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  upliftText: { textAlign: 'center', fontSize: 14, fontWeight: '700', color: '#10B981', marginTop: 8 },

  phaseCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, borderLeftWidth: 4, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  phaseIconBig: { width: 44, height: 44, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  phaseName: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },

  promptBox: { backgroundColor: '#FDF2F8', borderRadius: 10, padding: 12, marginBottom: 10 },
  promptText: { fontSize: 14, color: '#831843', lineHeight: 22 },
  instructionText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20, marginBottom: 10, fontStyle: 'italic' },

  audioToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8, paddingVertical: 6 },
  audioToggleText: { fontSize: 13, fontWeight: '500', color: '#EC4899' },

  reflectionLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  reflectionInput: { backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, minHeight: 60, textAlignVertical: 'top' },

  phaseNav: { flexDirection: 'row', alignItems: 'center', marginTop: 14 },
  navBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: '#EC4899' },
  navBtnText: { fontSize: 13, fontWeight: '600', color: '#EC4899' },

  formLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4, marginTop: 4 },
  notesInput: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, minHeight: 48, textAlignVertical: 'top' },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#EC4899', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
