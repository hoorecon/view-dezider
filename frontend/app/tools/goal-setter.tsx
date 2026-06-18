import React, { useState, useCallback } from 'react';
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
import MetricsEditor, { type GoalMetric } from '../../src/components/MetricsEditor';
import SkillsetPicker from '../../src/components/SkillsetPicker';
import ResourcePicker, { type PickedResource } from '../../src/components/ResourcePicker';
import MilestoneEditor, { type SmartMilestone } from '../../src/components/MilestoneEditor';
import TimestampLine from '../../src/components/TimestampLine';
import { CollabBar } from '../../src/components/CollabBar';
import { DecisionContinuePanel } from '../../src/components/DecisionContinuePanel';
import api from '../../src/utils/api';

const AUDIO_URL = 'https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/unvj7j0c_Goal%20Setter.mp3';

const SMART_FIELDS = [
  { id: 'specific', letter: 'S', name: 'Specific', color: '#3B82F6', prompt: 'What exactly do you want to achieve?', hint: 'Be precise about the outcome' },
  { id: 'measurable', letter: 'M', name: 'Measurable', color: '#10B981', prompt: 'How will you measure success?', hint: 'Define the metric' },
  { id: 'achievable', letter: 'A', name: 'Achievable', color: '#F59E0B', prompt: 'Is it achievable with current capabilities?', hint: 'Skills, knowledge, finances, support' },
  { id: 'realistic', letter: 'R', name: 'Realistic', color: '#8B5CF6', prompt: 'Is it realistic in your environment?', hint: 'Market, competition, timing' },
  { id: 'timebound', letter: 'T', name: 'Time-bound', color: '#EF4444', prompt: 'What is the timeline & milestones?', hint: 'Deadlines and interim checkpoints' },
];

export default function GoalSetterScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<'list' | 'create'>('list');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [goals, setGoals] = useState<any[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);
  const [guideOpen, setGuideOpen] = useState(false);

  // Form
  const [title, setTitle] = useState('');
  const [challenge, setChallenge] = useState('');
  const [specific, setSpecific] = useState('');
  const [measurable, setMeasurable] = useState('');
  const [metrics, setMetrics] = useState<GoalMetric[]>([]);
  const [achievable, setAchievable] = useState('');
  const [achievableSkills, setAchievableSkills] = useState<string[]>([]);
  const [realistic, setRealistic] = useState('');
  const [realisticResources, setRealisticResources] = useState<PickedResource[]>([]);
  const [timebound, setTimebound] = useState('');
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [goalMilestones, setGoalMilestones] = useState<SmartMilestone[]>([]);
  // Phase 4 — bidirectional My-360 / Goals & Feels link
  const [lifeArea, setLifeArea] = useState<string>('');
  const [goalType, setGoalType] = useState<string>('');

  const fetchData = async () => {
    try {
      const [dashRes, goalsRes] = await Promise.all([
        api.get('/goal-setter/dashboard'),
        api.get('/goal-setter/goals'),
      ]);
      setDashboard(dashRes.data);
      setGoals(goalsRes.data || []);
    } catch (e) { console.error('Goal setter fetch:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const resetForm = () => {
    setTitle(''); setChallenge(''); setSpecific(''); setMeasurable('');
    setMetrics([]);
    setAchievable(''); setAchievableSkills([]);
    setRealistic(''); setRealisticResources([]);
    setTimebound('');
    setEditingGoalId(null);
    setGoalMilestones([]);
    setLifeArea(''); setGoalType('');
  };

  const handleSave = async () => {
    if (!title.trim()) { showAlert('Required', 'Enter a goal title'); return; }
    setSaving(true);
    try {
      const payload = {
        title: title.trim(), challenge: challenge.trim(),
        life_area: lifeArea, goal_type: goalType,
        specific, measurable, metrics,
        achievable, achievable_skills: achievableSkills,
        realistic, realistic_resources: realisticResources,
        timebound,
      };
      if (editingGoalId) {
        await api.put(`/goal-setter/goals/${editingGoalId}`, payload);
      } else {
        const res = await api.post('/goal-setter/goals', payload);
        // Promote draft milestones to server-side
        if (goalMilestones.length > 0 && res.data?.goal_id) {
          const gid = res.data.goal_id;
          for (const m of goalMilestones) {
            // Strip draft prefix; backend assigns a real milestone_id
            const { milestone_id: _drop, ...rest } = m as any;
            await api.post(`/goal-setter/goals/${gid}/milestones`, rest);
          }
        }
      }
      showAlert('Saved', 'SMART Goal created!');
      resetForm(); setMode('list'); fetchData();
    } catch (e) { showAlert('Error', 'Failed to save'); }
    finally { setSaving(false); }
  };

  const openEdit = async (id: string) => {
    try {
      const res = await api.get(`/goal-setter/goals/${id}`);
      const g = res.data;
      setTitle(g.title || ''); setChallenge(g.challenge || '');
      setLifeArea(g.life_area || ''); setGoalType(g.goal_type || '');
      setSpecific(g.specific || ''); setMeasurable(g.measurable || '');
      setMetrics(g.metrics || []);
      setAchievable(g.achievable || ''); setAchievableSkills(g.achievable_skills || []);
      setRealistic(g.realistic || ''); setRealisticResources(g.realistic_resources || []);
      setTimebound(g.timebound || '');
      setGoalMilestones(g.milestones || []);
      setEditingGoalId(id);
      setMode('create');
    } catch (e) { showAlert('Error', 'Failed to load goal'); }
  };

  const handleDelete = (id: string) => {
    showAlert('Delete', 'Remove this goal?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/goal-setter/goals/${id}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const smartValues = { specific, measurable, achievable, realistic, timebound };
  const smartSetters: Record<string, (v: string) => void> = {
    specific: setSpecific, measurable: setMeasurable, achievable: setAchievable,
    realistic: setRealistic, timebound: setTimebound,
  };

  const renderList = () => (
    <>
      {dashboard && (
        <View style={s.statsRow}>
          <View style={s.statBox}><Text style={s.statNum}>{dashboard.total_goals}</Text><Text style={s.statLabel}>Total</Text></View>
          <View style={s.statBox}><Text style={s.statNum}>{dashboard.active_goals}</Text><Text style={s.statLabel}>Active</Text></View>
          <View style={s.statBox}><Text style={s.statNum}>{dashboard.completed_goals}</Text><Text style={s.statLabel}>Done</Text></View>
          <View style={s.statBox}><Text style={s.statNum}>{dashboard.avg_progress}%</Text><Text style={s.statLabel}>Avg Progress</Text></View>
        </View>
      )}
      {goals.length === 0 ? (
        <View style={s.empty}>
          <View style={s.emptyIcon}><Ionicons name="flag-outline" size={48} color={COLORS.textMuted} /></View>
          <Text style={s.emptyTitle}>No SMART Goals Yet</Text>
          <Text style={s.emptySub}>Define what you want to achieve — focus on the WHAT, not the HOW</Text>
        </View>
      ) : (
        goals.map(g => (
          <TouchableOpacity key={g.goal_id} style={s.goalCard} activeOpacity={0.7} onPress={() => openEdit(g.goal_id)}>
            <View style={s.goalRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.goalTitle} numberOfLines={1}>{g.title}</Text>
                <Text style={s.goalSub}>{g.status} · {g.created_at?.split('T')[0]}</Text>
                <TimestampLine entity={g} compact />
              </View>
              <TouchableOpacity onPress={() => handleDelete(g.goal_id)}><Ionicons name="trash-outline" size={16} color={COLORS.textMuted} /></TouchableOpacity>
            </View>
            <View style={s.smartBar}>
              {SMART_FIELDS.map(f => (
                <View key={f.id} style={[s.smartDot, { backgroundColor: g[f.id] ? f.color : COLORS.divider }]}>
                  <Text style={[s.smartDotText, { color: g[f.id] ? '#FFF' : COLORS.textMuted }]}>{f.letter}</Text>
                </View>
              ))}
            </View>
          </TouchableOpacity>
        ))
      )}
    </>
  );

  const renderForm = () => (
    <>
      {/* Audio Guide */}
      <TouchableOpacity style={s.guideHeader} onPress={() => setGuideOpen(!guideOpen)}>
        <Ionicons name="headset" size={18} color="#059669" />
        <Text style={s.guideLabel}>Audio Guide: SMART Goals</Text>
        <Ionicons name={guideOpen ? 'chevron-up' : 'chevron-down'} size={16} color="#059669" />
      </TouchableOpacity>
      {guideOpen && (
        <View style={s.guideBody}>
          <AudioGuidePlayer uri={AUDIO_URL} title="Goal Setter — SMART Framework" color="#059669" />
          <Text style={s.guideText}>Focus on WHAT you really want without worrying about HOW. Define your best possible SMART goal for this challenge.</Text>
        </View>
      )}

      <Text style={s.formLabel}>Goal Title *</Text>
      <TextInput style={s.input} value={title} onChangeText={setTitle} placeholder="What is your goal?" placeholderTextColor={COLORS.textMuted} />

      <Text style={s.formLabel}>Life Area</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 6 }}>
        {[
          { code: 'holistic_health', label: 'Holistic Health' },
          { code: 'relationships', label: 'Relationships' },
          { code: 'career_business', label: 'Career / Business' },
          { code: 'finances', label: 'Finances' },
          { code: 'growth_learning', label: 'Growth & Learning' },
          { code: 'recreation', label: 'Recreation' },
          { code: 'contribution', label: 'Contribution' },
          { code: 'spirituality', label: 'Spirituality' },
          { code: 'environment', label: 'Environment' },
          { code: 'identity_purpose', label: 'Identity & Purpose' },
        ].map(la => (
          <TouchableOpacity key={la.code} onPress={() => setLifeArea(lifeArea === la.code ? '' : la.code)}
            style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1,
              borderColor: lifeArea === la.code ? '#059669' : '#CBD5E1',
              backgroundColor: lifeArea === la.code ? '#059669' : '#FFF', marginRight: 6 }}>
            <Text style={{ fontSize: 11, fontWeight: '700', color: lifeArea === la.code ? '#FFF' : '#475569' }}>{la.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={s.formLabel}>Goal Type</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
        {[
          { code: 'problem_resolution',     label: 'Problem Resolution',     color: '#DC2626' },
          { code: 'need_fulfillment',       label: 'Need Fulfillment',       color: '#EA580C' },
          { code: 'risk_management',        label: 'Risk Management',        color: '#7C3AED' },
          { code: 'aspiration_achievement', label: 'Aspiration Achievement', color: '#0EA5E9' },
        ].map(gt => {
          const on = goalType === gt.code;
          return (
            <TouchableOpacity key={gt.code} onPress={() => setGoalType(on ? '' : gt.code)}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1,
                borderColor: on ? gt.color : '#CBD5E1', backgroundColor: on ? gt.color : '#FFF' }}>
              <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={12} color={on ? '#FFF' : gt.color} />
              <Text style={{ fontSize: 11, fontWeight: '700', color: on ? '#FFF' : '#475569' }}>{gt.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={s.formLabel}>Challenge / Context</Text>
      <TextInput style={[s.input, { minHeight: 60 }]} value={challenge} onChangeText={setChallenge} placeholder="What challenge does this goal address?" placeholderTextColor={COLORS.textMuted} multiline />

      {/* SMART Fields */}
      {SMART_FIELDS.map(f => (
        <View key={f.id} style={s.smartField}>
          <View style={[s.smartLetterBadge, { backgroundColor: f.color }]}>
            <Text style={s.smartLetterText}>{f.letter}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.smartName}>{f.name}</Text>
            <Text style={s.smartPrompt}>{f.prompt}</Text>
            <TextInput style={s.smartInput} value={smartValues[f.id as keyof typeof smartValues]}
              onChangeText={smartSetters[f.id]} placeholder={f.hint}
              placeholderTextColor={COLORS.textMuted} multiline />
            {f.id === 'measurable' && (
              <View style={s.metricsWrap}>
                <View style={s.metricsHead}>
                  <Ionicons name="stats-chart" size={14} color="#059669" />
                  <Text style={s.metricsHeadText}>Structured Metrics ({metrics.length})</Text>
                </View>
                <Text style={s.metricsHelp}>
                  Define quantifiable metrics — each with name, unit, type, operator, target,
                  and who sets it. Mirrors Dezider's "Define Factor's Expected Value" step.
                </Text>
                <MetricsEditor value={metrics} onChange={setMetrics} />
              </View>
            )}
            {f.id === 'achievable' && (
              <View style={s.skillsWrap}>
                <SkillsetPicker value={achievableSkills} onChange={setAchievableSkills} />
              </View>
            )}
            {f.id === 'realistic' && (
              <View style={s.resourceWrap}>
                <ResourcePicker value={realisticResources} onChange={setRealisticResources} />
              </View>
            )}
          </View>
        </View>
      ))}

      {/* ── Milestones: recursive SMART grids under this Goal ── */}
      <View style={s.milestoneSection}>
        <View style={s.milestoneHead}>
          <Ionicons name="flag" size={16} color="#059669" />
          <Text style={s.milestoneTitle}>Milestones (Recursive SMART)</Text>
          <View style={s.milestoneBadge}><Text style={s.milestoneBadgeText}>{goalMilestones.length}</Text></View>
        </View>
        <Text style={s.milestoneHelp}>
          Break this goal into smaller SMART sub-goals to reach the metrics gradually.
          Each milestone has its own S·M·A·R·T grid + structured metrics. Once this
          Goal is linked to a GEM Goal, the milestones become read-only there
          (status & progress updates still possible).
        </Text>
        <MilestoneEditor
          goalId={editingGoalId}
          milestones={goalMilestones}
          onChange={setGoalMilestones}
        />
      </View>
    </>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#059669', '#10B981']} style={s.header}>
          <TouchableOpacity onPress={() => mode === 'create' ? setMode('list') : router.back()} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>Goal Setter</Text>
            <Text style={s.headerSub}>SMART Framework</Text>
          </View>
          {mode === 'list' && (
            <TouchableOpacity onPress={() => { resetForm(); setMode('create'); }} style={s.addBtn}>
              <Ionicons name="add" size={22} color="#FFF" />
            </TouchableOpacity>
          )}
        </LinearGradient>

        {loading ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}><ActivityIndicator size="large" color="#059669" /></View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: mode === 'create' ? 100 : 32 }}
            refreshControl={mode === 'list' ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined}>
            {/* Collab affordance — share goal definition or schedule a call.
                Only meaningful in edit mode (we have an editingGoalId). */}
            {mode === 'create' && editingGoalId && (
              <CollabBar
                module="goal-setter"
                decisionId={editingGoalId}
                stepId="s_define"
                stepLabel="SMART Goal"
                decisionTitle={undefined}
              />
            )}
            {mode === 'list' ? renderList() : renderForm()}
            {/* End-of-flow CTA — show only after saving (editingGoalId present). */}
            {mode === 'create' && editingGoalId && (
              <DecisionContinuePanel
                sourceModule="goal-setter"
                sourceDecisionId={editingGoalId}
                title="SMART goal"
                contextSummary="From your SMART goal definition."
              />
            )}
          </ScrollView>
        )}

        {mode === 'create' && (
          <View style={s.bottom}>
            <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <><Ionicons name="checkmark-circle" size={18} color="#FFF" /><Text style={s.saveBtnText}>Save SMART Goal</Text></>
              )}
            </TouchableOpacity>
          </View>
        )}

        {mode === 'list' && goals.length > 0 && (
          <View style={s.bottom}>
            <TouchableOpacity style={s.saveBtn} onPress={() => { resetForm(); setMode('create'); }}>
              <Ionicons name="add-circle" size={18} color="#FFF" /><Text style={s.saveBtnText}>New SMART Goal</Text>
            </TouchableOpacity>
          </View>
        )}
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
  addBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },

  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 16, fontWeight: '700', color: '#059669' },
  statLabel: { fontSize: 9, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  goalCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  goalRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  goalTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  goalSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  smartBar: { flexDirection: 'row', gap: 6 },
  smartDot: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  smartDotText: { fontSize: 11, fontWeight: '700' },

  guideHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14, backgroundColor: '#ECFDF5', borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: '#A7F3D0' },
  guideLabel: { flex: 1, fontSize: 13, fontWeight: '600', color: '#059669' },
  guideBody: { backgroundColor: '#F0FDF4', borderRadius: 12, padding: 14, marginBottom: 12 },
  guideText: { fontSize: 13, color: '#065F46', lineHeight: 20, fontStyle: 'italic', marginTop: 10 },

  formLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12, marginBottom: 4 },
  input: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary, textAlignVertical: 'top' },

  smartField: { flexDirection: 'row', gap: 10, marginTop: 14, alignItems: 'flex-start' },
  smartLetterBadge: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  smartLetterText: { fontSize: 16, fontWeight: '800', color: '#FFF' },
  smartName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  smartPrompt: { fontSize: 12, color: COLORS.textMuted, marginTop: 1, marginBottom: 4 },
  smartInput: { backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary, minHeight: 50, textAlignVertical: 'top' },

  metricsWrap: {
    marginTop: 10, padding: 10,
    backgroundColor: '#F0FDF4', borderRadius: 10,
    borderWidth: 1, borderColor: '#A7F3D0',
  },
  metricsHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  metricsHeadText: { fontSize: 12, fontWeight: '700', color: '#059669' },
  metricsHelp: { fontSize: 11, color: '#065F46', marginBottom: 8, lineHeight: 16 },
  skillsWrap: { marginTop: 10, padding: 10, backgroundColor: '#FFFBEB', borderRadius: 10, borderWidth: 1, borderColor: '#FDE68A' },
  resourceWrap: { marginTop: 10, padding: 10, backgroundColor: '#F5F3FF', borderRadius: 10, borderWidth: 1, borderColor: '#DDD6FE' },
  milestoneSection: { marginTop: 18, padding: 12, backgroundColor: '#ECFDF5', borderRadius: 12, borderWidth: 1, borderColor: '#A7F3D0' },
  milestoneHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  milestoneTitle: { flex: 1, fontSize: 14, fontWeight: '700', color: '#059669' },
  milestoneBadge: { backgroundColor: '#059669', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  milestoneBadgeText: { fontSize: 11, fontWeight: '700', color: '#FFFFFF' },
  milestoneHelp: { fontSize: 11, color: '#065F46', marginBottom: 10, lineHeight: 16 },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#059669', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
});
