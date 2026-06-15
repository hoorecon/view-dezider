import React, { useState, useCallback, useRef } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Modal, TextInput,
  KeyboardAvoidingView, Platform, Dimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import TimestampLine from '../../src/components/TimestampLine';
import TimingFieldset, { TimingValue } from '../../src/components/decisions/TimingFieldset';
import DecisionLinkPicker, { LinkSelection } from '../../src/components/decisions/DecisionLinkPicker';
import LinkedSourcePill from '../../src/components/decisions/LinkedSourcePill';
import { addDaysISO } from '../../src/utils/dateLocalize';
import VoiceInput, { VoiceSavedAudio } from '../../src/components/VoiceInput';
import AudioAttachment, { AudioAttachmentMeta } from '../../src/components/AudioAttachment';

const { width: SW } = Dimensions.get('window');

const STAGES = [
  { number: 1, id: 'crucial_check', name: 'Is This a Crucial Conversation?', icon: 'alert-circle', color: '#EF4444' },
  { number: 2, id: 'start_with_heart', name: 'Start with Heart', icon: 'heart', color: '#EC4899' },
  { number: 3, id: 'learn_to_look', name: 'Learn to Look', icon: 'eye', color: '#F59E0B' },
  { number: 4, id: 'make_it_safe', name: 'Make It Safe', icon: 'shield-checkmark', color: '#10B981' },
  { number: 5, id: 'master_my_story', name: 'Master My Story', icon: 'book', color: '#3B82F6' },
  { number: 6, id: 'speak_my_path', name: 'Speak My Path', icon: 'megaphone', color: '#8B5CF6' },
  { number: 7, id: 'explore_their_path', name: 'Explore Their Path', icon: 'ear', color: '#0EA5E9' },
  { number: 8, id: 'move_to_action', name: 'Move to Action', icon: 'rocket', color: '#F97316' },
  { number: 9, id: 'followup_closure', name: 'Follow-Up and Closure', icon: 'checkmark-done-circle', color: '#059669' },
];

const SILENCE = ['Avoiding','Withdrawing','Masking','Sugarcoating','Sarcasm','Delaying','Ghosting','Silent resentment'];
const VIOLENCE = ['Controlling','Labeling','Attacking','Interrupting','Threatening','Blaming','Shaming','Overstating','Forcing conclusion'];
const REPAIR_METHODS = [
  { id: 'apology', label: 'Apology', icon: 'hand-left', color: '#EC4899' },
  { id: 'contrasting', label: 'Contrasting', icon: 'swap-horizontal', color: '#8B5CF6' },
  { id: 'crib', label: 'CRIB (Mutual Purpose)', icon: 'people', color: '#10B981' },
];

const ACKNOWLEDGMENT = 'This tool is inspired by the dialogue principles in "Crucial Conversations" by Patterson, Grenny, McMillan & Switzler. Independent reflective implementation.';

// ─── VOICE CONTEXT (consumed by QField when voiceField is supplied) ────
type VoiceCtxValue = {
  sessionId: string;
  audioByField: Record<string, AudioAttachmentMeta[]>;
  onSaved: (audio: VoiceSavedAudio) => void;
  onDeleted: (audio_id: string) => void;
};
const VoiceCtx = React.createContext<VoiceCtxValue | null>(null);

// ─── QUESTION FIELD HELPER ────────────────────────────────────
function QField({ label, helper, value, onChangeText, multiline, placeholder, voiceField }: {
  label: string; helper?: string; value: string; onChangeText: (t: string) => void;
  multiline?: boolean; placeholder?: string; voiceField?: string;
}) {
  const voiceCtx = React.useContext(VoiceCtx);
  const showVoice = !!(voiceField && voiceCtx && voiceCtx.sessionId);
  const attachments = (showVoice && voiceField)
    ? (voiceCtx!.audioByField[voiceField] || []) : [];
  return (
    <View style={s.qField}>
      <View style={s.qLabelRow}>
        <Text style={s.qLabel}>{label}</Text>
        {showVoice && (
          <VoiceInput
            sessionId={voiceCtx!.sessionId}
            field={voiceField!}
            module="conflict-breaker"
            color="#003087"
            onTranscribed={(t) => {
              const cur = value || '';
              onChangeText(cur ? `${cur} ${t}`.trim() : t);
            }}
            onAudioSaved={voiceCtx!.onSaved}
          />
        )}
      </View>
      {helper ? <Text style={s.qHelper}>Example: {helper}</Text> : null}
      <TextInput
        style={[s.qInput, multiline && { height: 70, textAlignVertical: 'top' }]}
        value={value} onChangeText={onChangeText} multiline={multiline}
        placeholder={placeholder || 'Type here...'} placeholderTextColor="#6B7280"
      />
      {attachments.map((a) => (
        <AudioAttachment
          key={a.audio_id}
          audio={a}
          onDeleted={voiceCtx!.onDeleted}
        />
      ))}
    </View>
  );
}

// ─── SLIDER HELPER ────────────────────────────────────
function QSlider({ label, helper, value, onValue }: {
  label: string; helper?: string; value: number; onValue: (n: number) => void;
}) {
  return (
    <View style={s.qField}>
      <Text style={s.qLabel}>{label}: <Text style={{ color: '#FFF', fontSize: 18 }}>{value}</Text>/10</Text>
      {helper ? <Text style={s.qHelper}>Example: {helper}</Text> : null}
      <View style={s.sliderRow}>
        {[1,2,3,4,5,6,7,8,9,10].map(n => (
          <TouchableOpacity
            key={n}
            style={[s.sliderDot, value >= n && { backgroundColor: n <= 3 ? '#10B981' : n <= 6 ? '#F59E0B' : '#EF4444' }]}
            onPress={() => onValue(n)}
          >
            <Text style={[s.sliderNum, value >= n && { color: '#FFF' }]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ─── PATTERN SELECTOR ────────────────────────────────────
function PatternSelector({ label, options, selected, onToggle }: {
  label: string; options: string[]; selected: string[]; onToggle: (p: string) => void;
}) {
  return (
    <View style={s.qField}>
      <Text style={s.qLabel}>{label}</Text>
      <View style={s.patternGrid}>
        {options.map(p => (
          <TouchableOpacity
            key={p}
            style={[s.patternChip, selected.includes(p) && s.patternChipActive]}
            onPress={() => onToggle(p)}
          >
            <Text style={[s.patternText, selected.includes(p) && { color: '#FFF' }]}>{p}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN SCREEN
// ═══════════════════════════════════════════════════════════════

export default function ConflictBreakerScreen() {
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  // Active session
  const [activeSession, setActiveSession] = useState<any>(null);
  const [currentStage, setCurrentStage] = useState(0); // 0=list, 1-9=stages
  const [stageData, setStageData] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiOutput, setAiOutput] = useState('');

  // Create session modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ title: '', conversation_type: 'prepare', other_party_role: '' });
  // Enhancement #4/#5
  const [timing, setTiming] = useState<TimingValue>({ deadline_date: addDaysISO(7), impact_horizon_value: 7, impact_horizon_unit: 'days' });
  const [linkedSource, setLinkedSource] = useState<LinkSelection | null>(null);
  const [showLinkPicker, setShowLinkPicker] = useState(false);

  // Stage field data holders
  const [s1, setS1] = useState<any>({});
  const [s2, setS2] = useState<any>({});
  const [s3, setS3] = useState<any>({});
  const [s4, setS4] = useState<any>({});
  const [s5, setS5] = useState<any>({});
  const [s6, setS6] = useState<any>({});
  const [s7, setS7] = useState<any>({});
  const [s8, setS8] = useState<any>({});
  const [s9, setS9] = useState<any>({});

  // ─── Voice / audio attachments per field ──────────────────────────────
  const [audioByField, setAudioByField] = useState<Record<string, AudioAttachmentMeta[]>>({});

  const loadAudio = useCallback(async (sid: string) => {
    try {
      const res = await api.get(`/conflict-breaker/sessions/${sid}/audio`);
      const items: AudioAttachmentMeta[] = res.data?.items || [];
      const grouped: Record<string, AudioAttachmentMeta[]> = {};
      for (const it of items) {
        const f = it.field || '_';
        if (!grouped[f]) grouped[f] = [];
        grouped[f].push(it);
      }
      setAudioByField(grouped);
    } catch (e) {
      console.error('audio load failed', e);
      setAudioByField({});
    }
  }, []);

  const handleAudioSaved = useCallback((a: VoiceSavedAudio) => {
    setAudioByField(prev => {
      const next = { ...prev };
      const list = next[a.field] ? [...next[a.field]] : [];
      list.push({
        audio_id: a.audio_id,
        field: a.field,
        ext: a.ext,
        size_bytes: a.size_bytes,
        duration_sec: a.duration_sec,
        credits_charged: a.credits_charged,
        retention_days: a.retention_days,
      });
      next[a.field] = list;
      return next;
    });
  }, []);

  const handleAudioDeleted = useCallback((audio_id: string) => {
    setAudioByField(prev => {
      const next: Record<string, AudioAttachmentMeta[]> = {};
      for (const [k, list] of Object.entries(prev)) {
        next[k] = list.filter(a => a.audio_id !== audio_id);
      }
      return next;
    });
  }, []);

  const voiceCtxValue = activeSession
    ? { sessionId: activeSession.session_id, audioByField,
        onSaved: handleAudioSaved, onDeleted: handleAudioDeleted }
    : null;

  const fetchSessions = async () => {
    try {
      const res = await api.get('/conflict-breaker/sessions');
      setSessions(res.data || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchSessions(); }, []));

  const onRefresh = async () => { setRefreshing(true); await fetchSessions(); setRefreshing(false); };

  const openSession = async (session: any) => {
    setActiveSession(session);
    setCurrentStage(session.current_stage || 1);
    // Load full session data
    try {
      const res = await api.get(`/conflict-breaker/sessions/${session.session_id}/full`);
      const d = res.data;
      setS1(d.crucial_check || {});
      setS2(d.motive_clarity || {});
      setS3(d.safety_diagnosis || {});
      setS4(d.make_safe || {});
      setS5(d.story_map || {});
      setS6(d.script_builder || {});
      setS7(d.listening_plan || {});
      setS8(d.action_plan || {});
      setS9(d.closure || {});
      // load attached voice clips for this session
      loadAudio(session.session_id);
    } catch (e) { console.error(e); }
    setAiOutput('');
  };

  const createSession = async () => {
    if (!createForm.title.trim()) return showAlert('Error', 'Title required');
    try {
      const res = await api.post('/conflict-breaker/sessions', {
        ...createForm,
        deadline_date: timing.deadline_date,
        impact_horizon_value: timing.impact_horizon_value,
        impact_horizon_unit: timing.impact_horizon_unit,
        linked_from_decision_id: linkedSource?.linked_from_decision_id || null,
        linked_from_module: linkedSource?.linked_from_module || null,
        linked_from_option_label: linkedSource?.linked_from_option_label || null,
        linked_from_score_pct: linkedSource?.linked_from_score_pct ?? null,
      });
      setShowCreate(false);
      openSession(res.data);
    } catch (e) { showAlert('Error', 'Failed to create'); }
  };

  const deleteSession = (sid: string) => {
    showAlert('Delete', 'Delete this session and all data?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/conflict-breaker/sessions/${sid}`); fetchSessions(); }
        catch (e) { showAlert('Error', 'Failed'); }
      }},
    ]);
  };

  // ─── SAVE STAGE ────────────────────────────────────
  const saveStage = async () => {
    if (!activeSession) return;
    setSaving(true);
    const sid = activeSession.session_id;
    try {
      const endpoints: Record<number, { url: string; data: any }> = {
        1: { url: `/conflict-breaker/sessions/${sid}/crucial-check`, data: s1 },
        2: { url: `/conflict-breaker/sessions/${sid}/motive-clarity`, data: s2 },
        3: { url: `/conflict-breaker/sessions/${sid}/safety-diagnosis`, data: s3 },
        4: { url: `/conflict-breaker/sessions/${sid}/make-safe`, data: s4 },
        5: { url: `/conflict-breaker/sessions/${sid}/story-map`, data: s5 },
        6: { url: `/conflict-breaker/sessions/${sid}/script-builder`, data: s6 },
        7: { url: `/conflict-breaker/sessions/${sid}/listening-plan`, data: s7 },
        8: { url: `/conflict-breaker/sessions/${sid}/action-plan`, data: s8 },
        9: { url: `/conflict-breaker/sessions/${sid}/closure`, data: s9 },
      };
      const ep = endpoints[currentStage];
      if (ep) await api.post(ep.url, ep.data);
      showAlert('Saved', 'Stage data saved');
    } catch (e) { showAlert('Error', 'Save failed'); }
    finally { setSaving(false); }
  };

  const generateAI = async () => {
    if (!activeSession) return;
    setAiLoading(true); setAiOutput('');
    const stageIds: Record<number, string> = {
      1: 'crucial_check', 2: 'motive_clarity', 3: 'safety_diagnosis',
      4: 'make_safe', 5: 'story_map', 6: 'script_builder',
      7: 'listening_plan', 8: 'action_plan', 9: 'report',
    };
    try {
      // Save first
      await saveStage();
      const res = await api.post(`/conflict-breaker/sessions/${activeSession.session_id}/ai-generate/${stageIds[currentStage]}`, {});
      setAiOutput(res.data.ai_output || '');
    } catch (e) { showAlert('Error', 'AI generation failed'); }
    finally { setAiLoading(false); }
  };

  const goNext = async () => {
    await saveStage();
    if (currentStage < 9) {
      setCurrentStage(currentStage + 1);
      setAiOutput('');
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    }
  };

  const goPrev = () => {
    if (currentStage > 1) {
      setCurrentStage(currentStage - 1);
      setAiOutput('');
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    }
  };

  // ═══════════════════════════════════════════════════
  // STAGE RENDERERS
  // ═══════════════════════════════════════════════════

  const renderStage1 = () => (
    <>
      <QField label="What is the conversation about?" helper='"I need to talk to my co-founder about missed commitments."'
        value={s1.about || ''} onChangeText={t => setS1({ ...s1, about: t })} multiline voiceField="about" />
      <QField label="Who is involved?" helper='"My spouse, business partner, employee, investor, or team member."'
        value={s1.who_involved || ''} onChangeText={t => setS1({ ...s1, who_involved: t })} voiceField="who_involved" />
      <QField label="What is at stake?" helper='"Trust, money, deadline, relationship, or personal dignity."'
        value={s1.at_stake || ''} onChangeText={t => setS1({ ...s1, at_stake: t })} multiline voiceField="at_stake" />
      <QField label="Are opinions different?" helper='"I think the issue is serious, but they may feel I am overreacting."'
        value={s1.opinions_differ || ''} onChangeText={t => setS1({ ...s1, opinions_differ: t })} multiline voiceField="opinions_differ" />
      <QField label="Are emotions strong?" helper='"I feel angry, hurt, afraid, ignored, or defensive."'
        value={s1.emotions_strong || ''} onChangeText={t => setS1({ ...s1, emotions_strong: t })} multiline voiceField="emotions_strong" />
      <QField label="What may happen if you avoid this?" helper='"The problem may repeat, resentment may build."'
        value={s1.if_avoid || ''} onChangeText={t => setS1({ ...s1, if_avoid: t })} multiline voiceField="if_avoid" />
      <QField label="What may happen if handled poorly?" helper='"The other person may become defensive, trust may reduce."'
        value={s1.if_handle_poorly || ''} onChangeText={t => setS1({ ...s1, if_handle_poorly: t })} multiline voiceField="if_handle_poorly" />
      <QField label="What result do you want?" helper='"Clarity, accountability, mutual respect, and a practical next step."'
        value={s1.desired_result || ''} onChangeText={t => setS1({ ...s1, desired_result: t })} multiline voiceField="desired_result" />

      <Text style={s.subHeader}>Intensity Sliders</Text>
      <QSlider label="Stakes Level" helper='"1=minor, 10=major impact"'
        value={s1.stakes_score || 5} onValue={n => setS1({ ...s1, stakes_score: n })} />
      <QSlider label="Emotional Intensity" helper='"1=calm, 10=emotionally overloaded"'
        value={s1.emotion_score || 5} onValue={n => setS1({ ...s1, emotion_score: n })} />
      <QSlider label="Opinion Difference" helper='"1=mostly aligned, 10=completely opposite"'
        value={s1.opinion_difference_score || 5} onValue={n => setS1({ ...s1, opinion_difference_score: n })} />
      <QSlider label="Relationship Sensitivity" helper='"1=low risk, 10=deeply affects trust"'
        value={s1.relationship_sensitivity_score || 5} onValue={n => setS1({ ...s1, relationship_sensitivity_score: n })} />
      <QSlider label="Urgency" helper='"1=can wait, 10=must be addressed soon"'
        value={s1.urgency_score || 5} onValue={n => setS1({ ...s1, urgency_score: n })} />
    </>
  );

  const renderStage2 = () => (
    <>
      <QField label="What do I really want for myself?" helper='"I want to be heard without losing self-respect."'
        value={s2.want_for_self || ''} onChangeText={t => setS2({ ...s2, want_for_self: t })} multiline voiceField="want_for_self" />
      <QField label="What do I really want for the other person?" helper='"I want them to understand without feeling attacked."'
        value={s2.want_for_other || ''} onChangeText={t => setS2({ ...s2, want_for_other: t })} multiline voiceField="want_for_other" />
      <QField label="What do I really want for the relationship?" helper='"I want trust to remain intact."'
        value={s2.want_for_relationship || ''} onChangeText={t => setS2({ ...s2, want_for_relationship: t })} multiline voiceField="want_for_relationship" />
      <QField label="What do I want for the project/family/team?" helper='"I want work to move forward without hidden resentment."'
        value={s2.want_for_project_or_family || ''} onChangeText={t => setS2({ ...s2, want_for_project_or_family: t })} multiline voiceField="want_for_project_or_family" />
      <QField label="What result should NOT be damaged?" helper='"I should not damage long-term collaboration just to win."'
        value={s2.result_not_to_damage || ''} onChangeText={t => setS2({ ...s2, result_not_to_damage: t })} multiline voiceField="result_not_to_damage" />
      <QField label="Am I trying to win, punish, prove, escape, or genuinely solve?" helper='"Am I speaking to solve, or to make them feel wrong?"'
        value={s2.am_i_trying_to || ''} onChangeText={t => setS2({ ...s2, am_i_trying_to: t })} multiline voiceField="am_i_trying_to" />
      <QField label="How would I behave if I truly wanted the above result?" helper='"I would speak calmly, ask questions, avoid personal attacks."'
        value={s2.ideal_behavior || ''} onChangeText={t => setS2({ ...s2, ideal_behavior: t })} multiline voiceField="ideal_behavior" />

      <Text style={s.subHeader}>Sucker&apos;s Choice Detector</Text>
      <QField label="What do I want?" helper='"I want accountability."'
        value={s2.what_i_want || ''} onChangeText={t => setS2({ ...s2, what_i_want: t })} voiceField="what_i_want" />
      <QField label="What do I NOT want?" helper='"I do not want them to feel insulted."'
        value={s2.what_i_do_not_want || ''} onChangeText={t => setS2({ ...s2, what_i_do_not_want: t })} voiceField="what_i_do_not_want" />
      <QField label="How can I achieve both? (AND statement)" helper='"I can speak factually and respectfully, while inviting their view."'
        value={s2.and_statement || ''} onChangeText={t => setS2({ ...s2, and_statement: t })} multiline voiceField="and_statement" />
    </>
  );

  const renderStage3 = () => {
    const togglePattern = (arr: string[], p: string, setter: Function, key: string) => {
      const cur = arr || [];
      const next = cur.includes(p) ? cur.filter((x: string) => x !== p) : [...cur, p];
      setter((prev: any) => ({ ...prev, [key]: next }));
    };
    return (
      <>
        <QField label="What is the visible topic?" helper='"Missed deadline, money issue, broken promise."'
          value={s3.visible_topic || ''} onChangeText={t => setS3({ ...s3, visible_topic: t })} multiline voiceField="visible_topic" />
        <QField label="What is the hidden emotional issue?" helper='"I feel ignored, taken for granted, controlled."'
          value={s3.hidden_emotional_issue || ''} onChangeText={t => setS3({ ...s3, hidden_emotional_issue: t })} multiline voiceField="hidden_emotional_issue" />
        <QField label="What body signals are you noticing?" helper='"Tight chest, fast heartbeat, tense jaw."'
          value={s3.body_signals || ''} onChangeText={t => setS3({ ...s3, body_signals: t })} voiceField="body_signals" />
        <QField label="What emotion is rising?" helper='"Anger, fear, hurt, shame, disappointment."'
          value={s3.emotion_rising || ''} onChangeText={t => setS3({ ...s3, emotion_rising: t })} voiceField="emotion_rising" />
        <QField label="What behavior are you showing?" helper='"Delaying, avoiding, overexplaining, being sarcastic."'
          value={s3.behavior_showing || ''} onChangeText={t => setS3({ ...s3, behavior_showing: t })} voiceField="behavior_showing" />

        <PatternSelector label="Your Silence Patterns" options={SILENCE}
          selected={s3.user_subpatterns || []}
          onToggle={p => togglePattern(s3.user_subpatterns, p, setS3, 'user_subpatterns')} />
        <PatternSelector label="Your Violence Patterns" options={VIOLENCE}
          selected={s3.other_subpatterns || []}
          onToggle={p => togglePattern(s3.other_subpatterns, p, setS3, 'other_subpatterns')} />
      </>
    );
  };

  const renderStage4 = () => (
    <>
      <QField label="Is Mutual Purpose at risk?" helper='"They may feel I only want my way."'
        value={s4.mutual_purpose_at_risk || ''} onChangeText={t => setS4({ ...s4, mutual_purpose_at_risk: t })} multiline voiceField="mutual_purpose_at_risk" />
      <QField label="Is Mutual Respect at risk?" helper='"They may feel judged or looked down upon."'
        value={s4.mutual_respect_at_risk || ''} onChangeText={t => setS4({ ...s4, mutual_respect_at_risk: t })} multiline voiceField="mutual_respect_at_risk" />
      <QField label="Did I hurt, dismiss, or ignore them?" helper='"I may have spoken harshly or delayed replying."'
        value={s4.did_i_hurt || ''} onChangeText={t => setS4({ ...s4, did_i_hurt: t })} multiline voiceField="did_i_hurt" />
      <QField label="Did they misunderstand my intention?" helper='"They may think I am attacking, while I only want clarity."'
        value={s4.misunderstood_intention || ''} onChangeText={t => setS4({ ...s4, misunderstood_intention: t })} multiline voiceField="misunderstood_intention" />

      <Text style={s.subHeader}>Choose Safety Repair Method</Text>
      <View style={s.repairRow}>
        {REPAIR_METHODS.map(m => (
          <TouchableOpacity key={m.id}
            style={[s.repairBtn, s4.safety_repair_method === m.id && { backgroundColor: m.color, borderColor: m.color }]}
            onPress={() => setS4({ ...s4, safety_repair_method: m.id })}>
            <Ionicons name={m.icon as any} size={18} color={s4.safety_repair_method === m.id ? '#FFF' : m.color} />
            <Text style={[s.repairText, s4.safety_repair_method === m.id && { color: '#FFF' }]}>{m.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {s4.safety_repair_method === 'apology' && (
        <>
          <QField label="What did I do or fail to do?" helper='"I did not inform them on time."'
            value={s4.apology_what_i_did || ''} onChangeText={t => setS4({ ...s4, apology_what_i_did: t })} multiline voiceField="apology_what_i_did" />
          <QField label="How did it affect them?" helper='"They had to wait, redo work, or felt disrespected."'
            value={s4.apology_how_affected || ''} onChangeText={t => setS4({ ...s4, apology_how_affected: t })} multiline voiceField="apology_how_affected" />
          <QField label="Your apology draft" helper='"I am sorry I did not update you."'
            value={s4.apology_draft || ''} onChangeText={t => setS4({ ...s4, apology_draft: t })} multiline voiceField="apology_draft" />
        </>
      )}

      {s4.safety_repair_method === 'contrasting' && (
        <>
          <QField label="What might they wrongly think I mean?" helper='"They may think I am saying they are careless."'
            value={s4.contrast_they_wrongly_think || ''} onChangeText={t => setS4({ ...s4, contrast_they_wrongly_think: t })} multiline voiceField="contrast_they_wrongly_think" />
          <QField label="What do I actually mean?" helper='"I am saying this specific action created a problem."'
            value={s4.contrast_i_actually_mean || ''} onChangeText={t => setS4({ ...s4, contrast_i_actually_mean: t })} multiline voiceField="contrast_i_actually_mean" />
        </>
      )}

      {s4.safety_repair_method === 'crib' && (
        <>
          <QField label="What am I asking for?" helper='"I want the report completed by Friday."'
            value={s4.crib_what_i_ask || ''} onChangeText={t => setS4({ ...s4, crib_what_i_ask: t })} multiline voiceField="crib_what_i_ask" />
          <QField label="Why do I want it?" helper='"The investor review depends on it."'
            value={s4.crib_why_i_want || ''} onChangeText={t => setS4({ ...s4, crib_why_i_want: t })} voiceField="crib_why_i_want" />
          <QField label="What are they asking for?" helper='"They want more time."'
            value={s4.crib_what_they_ask || ''} onChangeText={t => setS4({ ...s4, crib_what_they_ask: t })} voiceField="crib_what_they_ask" />
          <QField label="Why might they want it?" helper='"Worried about quality or workload."'
            value={s4.crib_why_they_want || ''} onChangeText={t => setS4({ ...s4, crib_why_they_want: t })} voiceField="crib_why_they_want" />
          <QField label="Higher shared purpose?" helper='"We both want a strong report without last-minute errors."'
            value={s4.crib_higher_purpose || ''} onChangeText={t => setS4({ ...s4, crib_higher_purpose: t })} multiline voiceField="crib_higher_purpose" />
          <QField label="Possible win-win option?" helper='"Submit draft by Friday, final by Monday."'
            value={s4.crib_new_option || ''} onChangeText={t => setS4({ ...s4, crib_new_option: t })} multiline voiceField="crib_new_option" />
        </>
      )}
    </>
  );

  const renderStage5 = () => (
    <>
      <Text style={s.subHeader}>Path to Action: See/Hear → Story → Feeling → Action</Text>
      <QField label="What exactly did I see or hear? (FACTS)" helper='"They said tomorrow but did not send it."'
        value={s5.what_i_saw_heard || ''} onChangeText={t => setS5({ ...s5, what_i_saw_heard: t })} multiline voiceField="what_i_saw_heard" />
      <QField label="Observable facts (verifiable)" helper='"The meeting started 20 minutes late."'
        value={s5.observable_facts || ''} onChangeText={t => setS5({ ...s5, observable_facts: t })} multiline voiceField="observable_facts" />
      <QField label="What meaning did I add? (STORY)" helper='"I assumed they do not respect my time."'
        value={s5.meaning_i_added || ''} onChangeText={t => setS5({ ...s5, meaning_i_added: t })} multiline voiceField="meaning_i_added" />
      <QField label="What motive am I assuming?" helper='"They ignored me deliberately."'
        value={s5.assumed_motive || ''} onChangeText={t => setS5({ ...s5, assumed_motive: t })} voiceField="assumed_motive" />
      <QField label="What judgment or label?" helper='"Careless, arrogant, lazy, unreliable."'
        value={s5.label_used || ''} onChangeText={t => setS5({ ...s5, label_used: t })} voiceField="label_used" />
      <QField label="What emotion am I feeling?" helper='"Hurt, anger, fear, shame, betrayal."'
        value={s5.emotion || ''} onChangeText={t => setS5({ ...s5, emotion: t })} voiceField="emotion" />
      <QSlider label="Emotional Intensity" helper='"1=mild, 10=overwhelmed"'
        value={s5.emotional_intensity || 5} onValue={n => setS5({ ...s5, emotional_intensity: n })} />

      <Text style={s.subHeader}>Clever Story Detector</Text>
      <View style={s.storyTypeRow}>
        {['victim','villain','helpless','none'].map(st => (
          <TouchableOpacity key={st}
            style={[s.storyTypeBtn, s5.clever_story_type === st && s.storyTypeBtnActive]}
            onPress={() => setS5({ ...s5, clever_story_type: st })}>
            <Text style={[s.storyTypeText, s5.clever_story_type === st && { color: '#FFF' }]}>
              {st.charAt(0).toUpperCase() + st.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <QField label="Am I pretending not to notice my role?" helper='"Did I delay, assume, overreact, or fail to clarify?"'
        value={s5.my_role_in_problem || ''} onChangeText={t => setS5({ ...s5, my_role_in_problem: t })} multiline voiceField="my_role_in_problem" />
      <QField label="Why would a reasonable person act this way?" helper='"Maybe they were overloaded, unclear, or afraid."'
        value={s5.reasonable_person_reason || ''} onChangeText={t => setS5({ ...s5, reasonable_person_reason: t })} multiline voiceField="reasonable_person_reason" />
      <QField label="What alternative story is possible?" helper={'"Maybe the delay was not intentional."'}
        value={s5.alternative_story || ''} onChangeText={t => setS5({ ...s5, alternative_story: t })} multiline voiceField="alternative_story" />
    </>
  );

  const renderStage6 = () => (
    <>
      <Text style={s.subHeader}>STATE: Share facts → Tell story → Ask view → Talk tentatively → Encourage testing</Text>
      <QField label="Facts to begin with" helper='"The last two reports were submitted after deadline."'
        value={s6.facts_to_begin || ''} onChangeText={t => setS6({ ...s6, facts_to_begin: t })} multiline voiceField="facts_to_begin" />
      <QField label="My interpretation/concern" helper='"I am concerned this may affect investor confidence."'
        value={s6.my_interpretation || ''} onChangeText={t => setS6({ ...s6, my_interpretation: t })} multiline voiceField="my_interpretation" />
      <QField label="How to say this as possibility, not accusation?" helper='"I may be missing something, but I am worried that..."'
        value={s6.tentative_framing || ''} onChangeText={t => setS6({ ...s6, tentative_framing: t })} multiline voiceField="tentative_framing" />
      <QField label="Question to invite their view?" helper='"Can you help me understand from your side?"'
        value={s6.question_to_invite || ''} onChangeText={t => setS6({ ...s6, question_to_invite: t })} voiceField="question_to_invite" />
      <QField label="How to show openness to correction?" helper='"If I am reading this wrongly, please correct me."'
        value={s6.open_to_correction || ''} onChangeText={t => setS6({ ...s6, open_to_correction: t })} voiceField="open_to_correction" />
      <QField label="What to AVOID saying?" helper='"Avoid always, never, careless, useless, selfish."'
        value={s6.what_to_avoid || ''} onChangeText={t => setS6({ ...s6, what_to_avoid: t })} voiceField="what_to_avoid" />

      <Text style={s.subHeader}>Your Script</Text>
      <QField label="Final conversation script (or generate with AI)" helper=""
        value={s6.final_script || ''} onChangeText={t => setS6({ ...s6, final_script: t })} multiline voiceField="final_script" />
    </>
  );

  const renderStage7 = () => (
    <>
      <Text style={s.subHeader}>AMPP: Ask → Mirror → Paraphrase → Prime</Text>
      <QField label="ASK: What can I ask to understand their view?" helper='"Can you help me understand what happened from your side?"'
        value={s7.ask_question || ''} onChangeText={t => setS7({ ...s7, ask_question: t })} multiline voiceField="ask_question" />
      <QField label="MIRROR: What emotion do I notice in them?" helper='"You seem frustrated. Am I reading that correctly?"'
        value={s7.mirror_statement || ''} onChangeText={t => setS7({ ...s7, mirror_statement: t })} multiline voiceField="mirror_statement" />
      <QField label="PARAPHRASE: Restate what they said" helper='"So you are saying the deadline was unclear."'
        value={s7.paraphrase_statement || ''} onChangeText={t => setS7({ ...s7, paraphrase_statement: t })} multiline voiceField="paraphrase_statement" />
      <QField label="PRIME: If silent, gently offer concern" helper='"Are you worried I am blaming you?"'
        value={s7.prime_statement || ''} onChangeText={t => setS7({ ...s7, prime_statement: t })} multiline voiceField="prime_statement" />

      <Text style={s.subHeader}>What might they be...</Text>
      <QField label="Feeling?" helper='"Blamed, pressured, embarrassed, or misunderstood."'
        value={s7.what_they_feel || ''} onChangeText={t => setS7({ ...s7, what_they_feel: t })} voiceField="what_they_feel" />
      <QField label="Afraid of?" helper='"Punishment, rejection, loss of control."'
        value={s7.what_they_fear || ''} onChangeText={t => setS7({ ...s7, what_they_fear: t })} voiceField="what_they_fear" />
      <QField label="Wanting?" helper='"Fairness, time, recognition, clarity."'
        value={s7.what_they_want || ''} onChangeText={t => setS7({ ...s7, what_they_want: t })} voiceField="what_they_want" />

      <Text style={s.subHeader}>ABC Response</Text>
      <QField label="AGREE: Where do I agree?" helper='"I agree the timeline was tight."'
        value={s7.agree_points || ''} onChangeText={t => setS7({ ...s7, agree_points: t })} multiline voiceField="agree_points" />
      <QField label="BUILD: What can I add?" helper='"Along with that, we need earlier updates."'
        value={s7.build_points || ''} onChangeText={t => setS7({ ...s7, build_points: t })} multiline voiceField="build_points" />
      <QField label="COMPARE: Where do I see differently?" helper='"I see the workload, and also the update gap."'
        value={s7.compare_points || ''} onChangeText={t => setS7({ ...s7, compare_points: t })} multiline voiceField="compare_points" />
    </>
  );

  const renderStage8 = () => (
    <>
      <Text style={s.subHeader}>Decision Method</Text>
      <View style={s.storyTypeRow}>
        {['command','consult','vote','consensus','unclear'].map(dm => (
          <TouchableOpacity key={dm}
            style={[s.storyTypeBtn, s8.decision_method === dm && s.storyTypeBtnActive]}
            onPress={() => setS8({ ...s8, decision_method: dm })}>
            <Text style={[s.storyTypeText, s8.decision_method === dm && { color: '#FFF' }]}>
              {dm.charAt(0).toUpperCase() + dm.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <QField label="What decision was made?" helper='"We agreed to send weekly updates every Friday."'
        value={s8.final_decision || ''} onChangeText={t => setS8({ ...s8, final_decision: t })} multiline voiceField="final_decision" />
      <QField label="Who will do what?" helper='"Ravi prepares draft; I review."'
        value={s8.task || ''} onChangeText={t => setS8({ ...s8, task: t })} multiline voiceField="task" />
      <QField label="Owner" helper='"The task owner who will complete the action."'
        value={s8.owner || ''} onChangeText={t => setS8({ ...s8, owner: t })} voiceField="owner" />
      <QField label="By when?" helper='"By Tuesday 6 PM."'
        value={s8.deadline || ''} onChangeText={t => setS8({ ...s8, deadline: t })} voiceField="deadline" />
      <QField label="Resources needed?" helper='"Data, budget, login access, approval."'
        value={s8.resources_required || ''} onChangeText={t => setS8({ ...s8, resources_required: t })} voiceField="resources_required" />
      <QField label="Support required?" helper='"Help from finance, designer, mentor."'
        value={s8.support_required || ''} onChangeText={t => setS8({ ...s8, support_required: t })} voiceField="support_required" />
      <QField label="Follow-up date" helper='"Next Monday at 11 AM."'
        value={s8.followup_date || ''} onChangeText={t => setS8({ ...s8, followup_date: t })} voiceField="followup_date" />
      <QField label="How will completion be verified?" helper='"Document uploaded, email sent, task marked done."'
        value={s8.success_measure || ''} onChangeText={t => setS8({ ...s8, success_measure: t })} multiline voiceField="success_measure" />
      <QField label="Unresolved concerns" helper='"Delay risk if input data is late."'
        value={s8.unresolved_concerns || ''} onChangeText={t => setS8({ ...s8, unresolved_concerns: t })} multiline voiceField="unresolved_concerns" />
    </>
  );

  const renderStage9 = () => (
    <>
      <QField label="Was the conversation completed?" helper='"Did both sides say what needed to be said?"'
        value={s9.completed ? 'Yes' : (s9.completed === false ? 'No' : '')}
        onChangeText={t => setS9({ ...s9, completed: t.toLowerCase().startsWith('y') })} />
      <QField label="Any issue still unresolved?" helper='"One point may still need a separate discussion."'
        value={s9.unresolved_issue || ''} onChangeText={t => setS9({ ...s9, unresolved_issue: t })} multiline voiceField="unresolved_issue" />
      <QField label="Did both sides understand the decision?" helper='"Everyone knows what was agreed."'
        value={s9.both_understood || ''} onChangeText={t => setS9({ ...s9, both_understood: t })} voiceField="both_understood" />
      <QField label="Did anyone leave emotionally unsafe?" helper='"Someone may still feel blamed or unheard."'
        value={s9.anyone_unsafe || ''} onChangeText={t => setS9({ ...s9, anyone_unsafe: t })} multiline voiceField="anyone_unsafe" />
      <QField label="Personal learning from this conversation" helper='"I learned that starting with facts prevents defensiveness."'
        value={s9.personal_learning || ''} onChangeText={t => setS9({ ...s9, personal_learning: t })} multiline voiceField="personal_learning" />
      <QField label="What should be documented?" helper='"Decision, task, deadline, owner, pending issue."'
        value={s9.journal_content || ''} onChangeText={t => setS9({ ...s9, journal_content: t })} multiline voiceField="journal_content" />

      <Text style={s.subHeader}>Resolution Status</Text>
      <View style={s.storyTypeRow}>
        {['resolved','needs_repair','unresolved'].map(rs => (
          <TouchableOpacity key={rs}
            style={[s.storyTypeBtn, s9.resolved_status === rs && s.storyTypeBtnActive]}
            onPress={() => setS9({ ...s9, resolved_status: rs })}>
            <Text style={[s.storyTypeText, s9.resolved_status === rs && { color: '#FFF' }]}>
              {rs.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </>
  );

  const stageRenderers: Record<number, () => React.JSX.Element> = {
    1: renderStage1, 2: renderStage2, 3: renderStage3, 4: renderStage4,
    5: renderStage5, 6: renderStage6, 7: renderStage7, 8: renderStage8, 9: renderStage9,
  };

  // ═══════════════════════════════════════════════════
  // SESSION LIST VIEW
  // ═══════════════════════════════════════════════════

  const renderSessionList = () => (
    <>
      <LinearGradient colors={['#1E293B', '#0F172A']} style={s.heroBanner}>
        <Ionicons name="flash" size={32} color="#F97316" />
        <View style={{ marginLeft: 12, flex: 1 }}>
          <Text style={s.heroTitle}>The Conflict Breaker</Text>
          <Text style={s.heroSub}>Prepare for Crucial Conversations with clarity, safety, and respect.</Text>
        </View>
      </LinearGradient>

      <Text style={s.ackText}>{ACKNOWLEDGMENT}</Text>

      {/* Action Buttons */}
      <View style={s.actBtnRow}>
        {[
          { type: 'prepare', label: 'Prepare for a Conversation', icon: 'shield-checkmark', color: '#6366F1' },
          { type: 'repair', label: 'Repair a Conversation', icon: 'build', color: '#F59E0B' },
          { type: 'reflect', label: 'Reflect After a Conversation', icon: 'journal', color: '#10B981' },
        ].map(btn => (
          <TouchableOpacity key={btn.type} style={[s.actCard, { borderLeftColor: btn.color }]}
            onPress={() => { setCreateForm({ ...createForm, conversation_type: btn.type }); setShowCreate(true); }}>
            <Ionicons name={btn.icon as any} size={22} color={btn.color} />
            <Text style={s.actCardText}>{btn.label}</Text>
            <Ionicons name="chevron-forward" size={16} color="#6B7280" />
          </TouchableOpacity>
        ))}
      </View>

      {/* Sessions */}
      <Text style={s.sectionTitle}>Conversation Sessions ({sessions.length})</Text>
      {sessions.length === 0 ? (
        <View style={s.emptyState}>
          <Ionicons name="chatbubbles-outline" size={48} color="#6B7280" />
          <Text style={s.emptyText}>No sessions yet. Start preparing for a crucial conversation.</Text>
        </View>
      ) : (
        sessions.map(sess => {
          const stage = STAGES[(sess.current_stage || 1) - 1];
          return (
            <TouchableOpacity key={sess.session_id} style={s.sessCard} onPress={() => openSession(sess)}>
              <View style={[s.sessIcon, { backgroundColor: (stage?.color || '#6366F1') + '20' }]}>
                <Ionicons name={stage?.icon as any || 'chatbubble'} size={20} color={stage?.color || '#6366F1'} />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={s.sessTitle}>{sess.title || 'Untitled'}</Text>
                <Text style={s.sessSub}>Stage {sess.current_stage || 1}: {stage?.name || ''}</Text>
                <TimestampLine entity={sess} compact />
                <View style={s.sessMetaRow}>
                  <View style={[s.sessBadge, { backgroundColor: sess.status === 'completed' ? '#059669' : '#6366F1' }]}>
                    <Text style={s.sessBadgeText}>{sess.status || 'draft'}</Text>
                  </View>
                  <Text style={s.sessType}>{sess.conversation_type}</Text>
                </View>
              </View>
              <TouchableOpacity onPress={() => deleteSession(sess.session_id)} style={{ padding: 8 }}>
                <Ionicons name="trash-outline" size={18} color="#EF4444" />
              </TouchableOpacity>
            </TouchableOpacity>
          );
        })
      )}
    </>
  );

  // ═══════════════════════════════════════════════════
  // STAGE WIZARD VIEW
  // ═══════════════════════════════════════════════════

  const renderStageWizard = () => {
    const stage = STAGES[currentStage - 1];
    if (!stage) return null;
    return (
      <>
        {/* Progress */}
        <View style={s.progressRow}>
          {STAGES.map((st, i) => (
            <TouchableOpacity key={st.number}
              style={[s.progressDot, currentStage === st.number && { backgroundColor: st.color, transform: [{ scale: 1.3 }] },
                currentStage > st.number && { backgroundColor: '#059669' }]}
              onPress={() => { setCurrentStage(st.number); setAiOutput(''); scrollRef.current?.scrollTo({ y: 0 }); }}>
              <Text style={[s.progressNum, (currentStage >= st.number) && { color: '#FFF' }]}>{st.number}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Stage Header */}
        <View style={[s.stageHeader, { borderLeftColor: stage.color }]}>
          <Ionicons name={stage.icon as any} size={24} color={stage.color} />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={s.stageName}>{stage.name}</Text>
            <Text style={s.stageNum}>Stage {stage.number} of 9</Text>
          </View>
        </View>

        {/* Emotional intensity warning */}
        {s1.emotion_score >= 8 && currentStage <= 6 && (
          <View style={s.warnBanner}>
            <Ionicons name="warning" size={16} color="#FFF" />
            <Text style={s.warnText}>Pause before sending or speaking. First regulate, then communicate.</Text>
          </View>
        )}

        {/* Stage Content */}
        {stageRenderers[currentStage]?.()}

        {/* AI Output */}
        {aiOutput ? (
          <View style={s.aiBox}>
            <View style={s.aiHeader}>
              <Ionicons name="sparkles" size={18} color="#A78BFA" />
              <Text style={s.aiTitle}>AI Insight</Text>
            </View>
            <Text style={s.aiText}>{aiOutput}</Text>
          </View>
        ) : null}

        {/* Action Buttons */}
        <View style={s.navBtnRow}>
          {currentStage > 1 && (
            <TouchableOpacity style={s.navBtn} onPress={goPrev}>
              <Ionicons name="arrow-back" size={18} color="#FFF" />
              <Text style={s.navBtnText}>Previous</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity style={[s.navBtn, { backgroundColor: '#8B5CF6' }]} onPress={generateAI} disabled={aiLoading}>
            {aiLoading ? <ActivityIndicator color="#FFF" size="small" /> : (
              <>
                <Ionicons name="sparkles" size={18} color="#FFF" />
                <Text style={s.navBtnText}>{currentStage === 9 ? 'Generate Report' : 'AI Insight'}</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity style={[s.navBtn, { backgroundColor: '#059669' }]} onPress={goNext} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFF" size="small" /> : (
              <>
                <Text style={s.navBtnText}>{currentStage < 9 ? 'Next' : 'Complete'}</Text>
                <Ionicons name={currentStage < 9 ? 'arrow-forward' : 'checkmark'} size={18} color="#FFF" />
              </>
            )}
          </TouchableOpacity>
        </View>
      </>
    );
  };

  // ═══════════════════════════════════════════════════
  // MAIN RENDER
  // ═══════════════════════════════════════════════════

  if (loading) return (
    <SafeAreaView style={s.container}>
      <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView ref={scrollRef} contentContainerStyle={{ padding: 16, paddingBottom: 120 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>

          {/* Header */}
          <View style={s.header}>
            <TouchableOpacity onPress={() => {
              if (activeSession && currentStage > 0) {
                setActiveSession(null); setCurrentStage(0); fetchSessions();
              } else { router.back(); }
            }}>
              <Ionicons name="arrow-back" size={24} color="#FFF" />
            </TouchableOpacity>
            <Text style={s.headerTitle}>
              {activeSession ? (activeSession.title || 'Session') : 'The Conflict Breaker'}
            </Text>
            {activeSession && (
              <TouchableOpacity onPress={saveStage}>
                <Ionicons name="save" size={24} color="#FFF" />
              </TouchableOpacity>
            )}
          </View>

          {!activeSession ? renderSessionList() : (
            <VoiceCtx.Provider value={voiceCtxValue}>
              {renderStageWizard()}
            </VoiceCtx.Provider>
          )}

        </ScrollView>
      </KeyboardAvoidingView>

      {/* Create Modal */}
      <Modal visible={showCreate} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>New Conversation</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            <QField label="Title" helper='"Discuss project delay with partner"'
              value={createForm.title} onChangeText={t => setCreateForm({ ...createForm, title: t })} voiceField="title" />
            <QField label="Other party" helper='"Co-founder, spouse, manager, client"'
              value={createForm.other_party_role} onChangeText={t => setCreateForm({ ...createForm, other_party_role: t })} voiceField="other_party_role" />
            <TimingFieldset value={timing} onChange={setTiming} />
            {linkedSource ? (
              <LinkedSourcePill
                decision_id={linkedSource.linked_from_decision_id}
                module={linkedSource.linked_from_module}
                option_label={linkedSource.linked_from_option_label}
                score_pct={linkedSource.linked_from_score_pct ?? undefined}
                title={linkedSource.title}
                onRemove={() => setLinkedSource(null)}
              />
            ) : (
              <TouchableOpacity onPress={() => setShowLinkPicker(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 8, borderWidth: 1, borderColor: '#7C3AED', borderStyle: 'dashed', justifyContent: 'center', marginVertical: 6 }} testID="cb-link-from-prev">
                <Ionicons name="link-outline" size={12} color="#A78BFA" />
                <Text style={{ fontSize: 11, fontWeight: '600', color: '#A78BFA' }}>Link from previous decision</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity style={s.saveBtn} onPress={createSession}>
              <Text style={s.saveBtnText}>Start Preparation</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
      <DecisionLinkPicker visible={showLinkPicker} onClose={() => setShowLinkPicker(false)} onSelect={setLinkedSource} />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { color: '#FFF', fontSize: 17, fontWeight: '700', flex: 1, marginLeft: 12 },
  heroBanner: { borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  heroTitle: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  heroSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },
  ackText: { color: '#6B7280', fontSize: 10, marginBottom: 16, lineHeight: 14 },

  actBtnRow: { gap: 8, marginBottom: 16 },
  actCard: { backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderLeftWidth: 3, borderWidth: 1, borderColor: '#E2E8F0' },
  actCardText: { color: '#E2E8F0', fontSize: 14, fontWeight: '600', flex: 1 },

  sectionTitle: { color: '#FFF', fontSize: 16, fontWeight: '700', marginBottom: 12 },

  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyText: { color: '#6B7280', fontSize: 14, marginTop: 12, textAlign: 'center' },

  sessCard: { backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14, flexDirection: 'row', alignItems: 'center', marginBottom: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  sessIcon: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  sessTitle: { color: '#FFF', fontSize: 14, fontWeight: '600' },
  sessSub: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  sessMetaRow: { flexDirection: 'row', gap: 8, marginTop: 4, alignItems: 'center' },
  sessBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  sessBadgeText: { color: '#FFF', fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  sessType: { color: '#6B7280', fontSize: 11, textTransform: 'capitalize' },

  // Progress
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  progressDot: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#E2E8F0', justifyContent: 'center', alignItems: 'center' },
  progressNum: { color: '#6B7280', fontSize: 12, fontWeight: '700' },

  // Stage header
  stageHeader: { backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14, flexDirection: 'row', alignItems: 'center', marginBottom: 16, borderLeftWidth: 3, borderWidth: 1, borderColor: '#E2E8F0' },
  stageName: { color: '#FFF', fontSize: 16, fontWeight: '700' },
  stageNum: { color: '#94A3B8', fontSize: 12 },

  warnBanner: { backgroundColor: '#DC2626', borderRadius: 10, padding: 10, flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  warnText: { color: '#FFF', fontSize: 12, fontWeight: '600', flex: 1 },

  // Question fields
  qField: { marginBottom: 14 },
  qLabelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4, gap: 8 },
  qLabel: { color: '#E2E8F0', fontSize: 13, fontWeight: '600', marginBottom: 4 },
  qHelper: { color: '#6B7280', fontSize: 11, marginBottom: 6, fontStyle: 'italic' },
  qInput: { backgroundColor: '#FFFFFF', borderRadius: 10, borderWidth: 1, borderColor: '#CBD5E1', color: '#0F172A', paddingHorizontal: 12, paddingVertical: 10, fontSize: 14 },

  subHeader: { color: '#A78BFA', fontSize: 14, fontWeight: '700', marginTop: 16, marginBottom: 8 },

  // Slider
  sliderRow: { flexDirection: 'row', gap: 4, justifyContent: 'space-between' },
  sliderDot: { width: (SW - 80) / 10, height: 32, borderRadius: 6, backgroundColor: '#F1F5F9', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0' },
  sliderNum: { color: '#6B7280', fontSize: 11, fontWeight: '700' },

  // Pattern
  patternGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  patternChip: { borderRadius: 8, borderWidth: 1, borderColor: '#334155', paddingHorizontal: 10, paddingVertical: 6 },
  patternChipActive: { backgroundColor: '#003087', borderColor: '#003087' },
  patternText: { color: '#94A3B8', fontSize: 12, fontWeight: '500' },

  // Repair methods
  repairRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  repairBtn: { flex: 1, borderRadius: 10, borderWidth: 1.5, borderColor: '#334155', paddingVertical: 10, alignItems: 'center', gap: 4 },
  repairText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },

  // Story types
  storyTypeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  storyTypeBtn: { borderRadius: 8, borderWidth: 1, borderColor: '#334155', paddingHorizontal: 12, paddingVertical: 6 },
  storyTypeBtnActive: { backgroundColor: '#003087', borderColor: '#003087' },
  storyTypeText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },

  // AI output
  aiBox: { backgroundColor: '#EEF4FF', borderRadius: 14, padding: 16, marginTop: 16, borderWidth: 1, borderColor: '#BFD7FF' },
  aiHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  aiTitle: { color: '#A78BFA', fontSize: 14, fontWeight: '700' },
  aiText: { color: '#E2E8F0', fontSize: 13, lineHeight: 20 },

  // Navigation
  navBtnRow: { flexDirection: 'row', gap: 8, marginTop: 20 },
  navBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#64748B', borderRadius: 10, paddingVertical: 12 },
  navBtnText: { color: '#FFF', fontSize: 13, fontWeight: '600' },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#1E293B', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  saveBtn: { backgroundColor: '#6366F1', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 16 },
  saveBtnText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
