import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert, TextInput,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { handleAiError } from '../../src/utils/aiErrors';
import { formatAbsolute } from '../../src/utils/datetime';
import { confirmAiSpend, useAiEstimate } from '../../src/utils/aiEstimates';
import { AiCreditsBadge } from '../../src/components/AiCreditsBadge';

export default function EGSessionScreen() {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generatingReport, setGeneratingReport] = useState(false);
  const reportEst = useAiEstimate('eg_breakthrough_report');

  // Commitment form
  const [showCommit, setShowCommit] = useState(false);
  const [commitText, setCommitText] = useState('');
  const [commitType, setCommitType] = useState('immediate');
  const [savingCommit, setSavingCommit] = useState(false);

  // Journal form
  const [showJournal, setShowJournal] = useState(false);
  const [journalContent, setJournalContent] = useState('');
  const [savingJournal, setSavingJournal] = useState(false);

  const fetchSession = async () => {
    try {
      const res = await api.get(`/emotional-gatekeeper/sessions/${sessionId}`);
      setSession(res.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchSession(); }, [sessionId]);

  const handleGenerateReport = async () => {
    if (!(await confirmAiSpend('eg_breakthrough_report', 'Breakthrough report'))) return;
    setGeneratingReport(true);
    try {
      await api.post(`/emotional-gatekeeper/sessions/${sessionId}/report`);
      await fetchSession();
    } catch (err) { await handleAiError(err, { router, retry: handleGenerateReport }); }
    finally { setGeneratingReport(false); }
  };

  const handleAddCommitment = async () => {
    if (!commitText.trim()) return;
    setSavingCommit(true);
    try {
      await api.post(`/emotional-gatekeeper/sessions/${sessionId}/commitments`, {
        commitment_type: commitType, commitment_text: commitText,
      });
      setCommitText(''); setShowCommit(false);
      await fetchSession();
    } catch (err) { Alert.alert('Error', 'Failed to save commitment.'); }
    finally { setSavingCommit(false); }
  };

  const handleSaveJournal = async () => {
    if (!journalContent.trim()) return;
    setSavingJournal(true);
    try {
      await api.post(`/emotional-gatekeeper/sessions/${sessionId}/journal`, {
        journal_content: journalContent,
      });
      setShowJournal(false);
      await fetchSession();
    } catch (err) { Alert.alert('Error', 'Failed to save journal.'); }
    finally { setSavingJournal(false); }
  };

  const handleCompleteCommitment = async (commitId: string) => {
    try {
      await api.put(`/emotional-gatekeeper/commitments/${commitId}/complete`);
      await fetchSession();
    } catch (err) { Alert.alert('Error', 'Failed to complete.'); }
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container} edges={['top']}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#F59E0B" />
        </View>
      </SafeAreaView>
    );
  }

  if (!session) {
    return (
      <SafeAreaView style={st.container} edges={['top']}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 }}>
          <Text style={{ fontSize: 16, color: COLORS.textMuted }}>Session not found.</Text>
          <TouchableOpacity onPress={() => router.back()} style={{ marginTop: 16 }}>
            <Text style={{ color: COLORS.primary, fontWeight: '600' }}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const report = session.report?.report;
  const trapRef = session.trap_reflection;
  const loopRef = session.loop_reflection;
  const limRef = session.limitation_reflection;
  const aimRef = session.aim_reflection;
  const trapA = trapRef?.ai_summary;
  const loopR = loopRef?.ai_reframe_full;
  const limR = limRef?.ai_summary;
  const aimA = aimRef?.ai_analysis;
  const hasContent = !!(trapRef || loopRef || limRef || aimRef || session.outlet_reflection || report);
  const resumeRoutes: Record<string, string> = {
    trap: `/tools/eg-trap?sessionId=${session.id}`,
    loop: `/tools/eg-loop?sessionId=${session.id}`,
    limitation: `/tools/eg-limitation?sessionId=${session.id}`,
    outlet: `/tools/eg-outlet?sessionId=${session.id}`,
    aim: `/tools/eg-aim?sessionId=${session.id}`,
  };

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#D97706']} style={st.header}>
        <View style={st.headerTop}>
          <TouchableOpacity style={st.backBtn} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <AiCreditsBadge compact autoRefresh lowThreshold={reportEst ?? undefined} />
        </View>
        <Text style={st.headerTitle}>{session.title}</Text>
        <View style={st.headerMeta}>
          <View style={st.typeBadge}>
            <Text style={st.typeBadgeText}>{session.session_type?.toUpperCase()}</Text>
          </View>
          <Text style={st.headerDate}>{formatAbsolute(session.created_at)}</Text>
          <View style={[st.statusBadge, { backgroundColor: session.status === 'completed' ? '#10B981' : '#F59E0B' }]}>
            <Text style={st.statusText}>{session.status}</Text>
          </View>
        </View>
      </LinearGradient>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
        <View style={st.content}>
          {/* Per-session AI spend */}
          {(session.ai_cost?.credits || 0) > 0 && (
            <View style={st.aiCostRow} testID="session-ai-cost">
              <Ionicons name="sparkles" size={14} color="#7C3AED" />
              <Text style={st.aiCostText}>
                AI used this session: {session.ai_cost.credits} credit{session.ai_cost.credits === 1 ? '' : 's'}
                {session.ai_cost.calls ? ` • ${session.ai_cost.calls} call${session.ai_cost.calls === 1 ? '' : 's'}` : ''}
              </Text>
            </View>
          )}
          {/* Intensity */}
          {(session.intensity_before || session.intensity_after) && (
            <View style={st.intensityRow}>
              <View style={st.intensityItem}>
                <Text style={st.intensityNum}>{session.intensity_before || '-'}</Text>
                <Text style={st.intensityLabel}>Before</Text>
              </View>
              <Ionicons name="arrow-forward" size={20} color={COLORS.textMuted} />
              <View style={st.intensityItem}>
                <Text style={st.intensityNum}>{session.intensity_after || '-'}</Text>
                <Text style={st.intensityLabel}>After</Text>
              </View>
            </View>
          )}

          {/* What You Shared (captured inputs) */}
          {trapRef && (trapRef.situation || trapRef.category || trapRef.looping_thought) ? (
            <View style={st.insightCard} testID="session-trap-input">
              <Text style={st.insightTitle}>What You Shared</Text>
              {trapRef.situation ? (<><Text style={st.aLabel}>Situation</Text><Text style={st.aText}>{trapRef.situation}</Text></>) : null}
              {trapRef.category ? (<><Text style={st.aLabel}>Life Area</Text><Text style={st.aText}>{trapRef.category}</Text></>) : null}
              {typeof trapRef.intensity === 'number' ? (<><Text style={st.aLabel}>Intensity</Text><Text style={st.aText}>{trapRef.intensity}/10</Text></>) : null}
              {trapRef.external_trigger ? (<><Text style={st.aLabel}>External Trigger</Text><Text style={st.aText}>{trapRef.external_trigger}</Text></>) : null}
              {trapRef.internal_trigger ? (<><Text style={st.aLabel}>Internal Trigger</Text><Text style={st.aText}>{trapRef.internal_trigger}</Text></>) : null}
              {trapRef.linking_meaning ? (<><Text style={st.aLabel}>Meaning You Linked</Text><Text style={st.aText}>{trapRef.linking_meaning}</Text></>) : null}
              {trapRef.looping_thought ? (<><Text style={st.aLabel}>Looping Thought</Text><Text style={st.aText}>{trapRef.looping_thought}</Text></>) : null}
            </View>
          ) : null}

          {loopRef && (loopRef.repeated_thought || loopRef.emotion || loopRef.fear) ? (
            <View style={st.insightCard} testID="session-loop-input">
              <Text style={st.insightTitle}>What You Shared{loopR ? ' (Loop)' : ''}</Text>
              {loopRef.repeated_thought ? (<><Text style={st.aLabel}>Repeated Thought</Text><Text style={st.aText}>{loopRef.repeated_thought}</Text></>) : null}
              {loopRef.emotion ? (<><Text style={st.aLabel}>Emotion</Text><Text style={st.aText}>{loopRef.emotion}</Text></>) : null}
              {loopRef.repeat_count_today ? (<><Text style={st.aLabel}>Times Today</Text><Text style={st.aText}>{loopRef.repeat_count_today}</Text></>) : null}
              {loopRef.fear ? (<><Text style={st.aLabel}>Underlying Fear</Text><Text style={st.aText}>{loopRef.fear}</Text></>) : null}
              {loopRef.trying_to_solve ? (<><Text style={st.aLabel}>Trying to Solve</Text><Text style={st.aText}>{loopRef.trying_to_solve}</Text></>) : null}
            </View>
          ) : null}

          {limRef && (limRef.limitation_statement || limRef.why_limited) ? (
            <View style={st.insightCard} testID="session-lim-input">
              <Text style={st.insightTitle}>What You Shared{limR ? ' (Limitation)' : ''}</Text>
              {limRef.limitation_statement ? (<><Text style={st.aLabel}>Limitation</Text><Text style={st.aText}>{limRef.limitation_statement}</Text></>) : null}
              {limRef.why_limited ? (<><Text style={st.aLabel}>Why You Feel Limited</Text><Text style={st.aText}>{limRef.why_limited}</Text></>) : null}
              {limRef.origin ? (<><Text style={st.aLabel}>Origin</Text><Text style={st.aText}>{limRef.origin}</Text></>) : null}
              {limRef.belief_duration ? (<><Text style={st.aLabel}>Belief Duration</Text><Text style={st.aText}>{limRef.belief_duration}</Text></>) : null}
              {limRef.cost_of_limitation ? (<><Text style={st.aLabel}>Cost of This Limitation</Text><Text style={st.aText}>{limRef.cost_of_limitation}</Text></>) : null}
            </View>
          ) : null}

          {/* Incomplete session: nothing captured yet */}
          {!hasContent && (
            <View style={st.emptyCard} testID="session-incomplete">
              <Ionicons name="document-text-outline" size={40} color={COLORS.textMuted} />
              <Text style={st.emptyTitle}>This session is incomplete</Text>
              <Text style={st.emptySub}>You started this {session.session_type} session but did not record any reflections yet. Resume to continue where you left off.</Text>
              <TouchableOpacity
                style={st.resumeBtn}
                testID="session-resume-btn"
                onPress={() => router.push((resumeRoutes[session.session_type] || resumeRoutes.trap) as any)}>
                <Ionicons name="play" size={16} color="#FFF" />
                <Text style={st.resumeBtnText}>Resume Session</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* AI Analysis / Recommendations (captured during the session) */}
          {trapA && (
            <View style={st.insightCard} testID="session-trap-analysis">
              <Text style={st.insightTitle}>AI Trap Awareness</Text>
              {trapA.current_stage ? (
                <View style={st.stageBadge}>
                  <Text style={st.stageText}>Stage: {String(trapA.current_stage).toUpperCase()} ({Math.round((trapA.stage_confidence || 0) * 100)}%)</Text>
                </View>
              ) : null}
              {trapA.main_trigger ? (<><Text style={st.aLabel}>Main Trigger</Text><Text style={st.aText}>{trapA.main_trigger}</Text></>) : null}
              {trapA.repeated_thought ? (<><Text style={st.aLabel}>Repeated Thought</Text><Text style={st.aText}>{trapA.repeated_thought}</Text></>) : null}
              {trapA.emotional_amplification_pattern ? (<><Text style={st.aLabel}>How Emotions Are Amplified</Text><Text style={st.aText}>{trapA.emotional_amplification_pattern}</Text></>) : null}
              {trapA.false_problem_solving ? (<><Text style={st.aLabel}>False Problem-Solving</Text><Text style={st.aText}>{trapA.false_problem_solving}</Text></>) : null}
              {trapA.awareness_statement ? (
                <View style={st.amberBox}><Ionicons name="bulb" size={18} color="#D97706" /><Text style={st.amberText}>{trapA.awareness_statement}</Text></View>
              ) : null}
              {trapA.intervention ? (
                <View style={st.greenBox}>
                  <Ionicons name="medkit" size={18} color="#059669" />
                  <View style={{ flex: 1 }}>
                    <Text style={[st.greenText, { fontWeight: '700', marginBottom: 4 }]}>Recommended Intervention</Text>
                    <Text style={st.greenText}>{trapA.intervention.description}</Text>
                    {trapA.intervention.immediate_action ? <Text style={[st.greenText, { marginTop: 6, fontWeight: '600' }]}>→ {trapA.intervention.immediate_action}</Text> : null}
                  </View>
                </View>
              ) : null}
            </View>
          )}

          {loopR && (
            <View style={st.insightCard} testID="session-loop-reframe">
              <Text style={st.insightTitle}>Loop Reframe</Text>
              {loopR.emotional_driver ? (<><Text style={st.aLabel}>Emotional Driver</Text><Text style={st.aText}>{loopR.emotional_driver}</Text></>) : null}
              {loopR.method_applied ? (<><Text style={st.aLabel}>Method Applied</Text><Text style={st.aText}>{loopR.method_applied}</Text></>) : null}
              {loopR.new_perspective ? (<View style={st.highlightBox}><Ionicons name="sparkles" size={18} color="#7C3AED" /><Text style={st.highlightText}>{loopR.new_perspective}</Text></View>) : null}
              {loopR.calming_statement ? (<View style={st.greenBox}><Ionicons name="heart" size={16} color="#059669" /><Text style={st.greenText}>{loopR.calming_statement}</Text></View>) : null}
              {loopR.immediate_action ? (<View style={st.amberBox}><Ionicons name="flash" size={16} color="#D97706" /><Text style={st.amberText}>{loopR.immediate_action}</Text></View>) : null}
              {loopR.reflection_affirmation ? (<Text style={st.affirm}>&ldquo;{loopR.reflection_affirmation}&rdquo;</Text>) : null}
            </View>
          )}

          {limR && (
            <View style={st.insightCard} testID="session-limitation-breakthrough">
              <Text style={st.insightTitle}>Limitation Breakthrough</Text>
              {limR.old_belief ? (<><Text style={st.aLabel}>Old Belief</Text><Text style={st.oldBelief}>{limR.old_belief}</Text></>) : null}
              {limR.new_belief ? (<><Text style={st.aLabel}>New Empowering Belief</Text><Text style={[st.aText, { color: '#047857', fontWeight: '600' }]}>{limR.new_belief}</Text></>) : null}
              {limR.growth_evidence ? (<><Text style={st.aLabel}>Growth Evidence</Text><Text style={st.aText}>{limR.growth_evidence}</Text></>) : null}
              {limR.reframe_statement ? (<View style={st.highlightBox}><Ionicons name="sparkles" size={18} color="#1D4ED8" /><Text style={[st.highlightText, { color: '#1E40AF' }]}>{limR.reframe_statement}</Text></View>) : null}
              {limR.suggested_action ? (
                <View style={st.amberBox}><Ionicons name="flash" size={16} color="#D97706" />
                  <View style={{ flex: 1 }}>
                    <Text style={st.amberText}>{limR.suggested_action}</Text>
                    {limR.action_timeline ? <Text style={[st.amberText, { fontSize: 11, marginTop: 2 }]}>Timeline: {limR.action_timeline}</Text> : null}
                  </View>
                </View>
              ) : null}
              {limR.affirmation ? (<Text style={[st.affirm, { color: '#1D4ED8' }]}>&ldquo;{limR.affirmation}&rdquo;</Text>) : null}
            </View>
          )}

          {aimA && (
            <View style={st.insightCard} testID="session-aim-analysis">
              <Text style={st.insightTitle}>AIM Analysis</Text>
              {aimA.self_awareness_summary ? (<View style={st.amberBox}><Ionicons name="bulb" size={18} color="#EA580C" /><Text style={st.amberText}>{aimA.self_awareness_summary}</Text></View>) : null}
              {aimA.addictions_analysis?.map((a: any, i: number) => (
                <View key={`a${i}`} style={st.subItem}>
                  <View style={st.subHead}><Ionicons name="flame" size={14} color="#F97316" /><Text style={st.subName}>{a.addiction}</Text></View>
                  {a.root_pattern ? <Text style={st.aText}>Root: {a.root_pattern}</Text> : null}
                  {a.corrective_action ? <Text style={st.aText}>Action: {a.corrective_action}</Text> : null}
                  {a.replacement_behavior ? <Text style={st.aText}>Replace with: {a.replacement_behavior}</Text> : null}
                </View>
              ))}
              {aimA.irritations_analysis?.map((ir: any, i: number) => (
                <View key={`i${i}`} style={st.subItem}>
                  <View style={st.subHead}><Ionicons name="thunderstorm" size={14} color="#EF4444" /><Text style={st.subName}>{ir.irritation}</Text></View>
                  {ir.reaction_pattern ? <Text style={st.aText}>Pattern: {ir.reaction_pattern}</Text> : null}
                  {ir.constructive_response ? <Text style={st.aText}>Response: {ir.constructive_response}</Text> : null}
                </View>
              ))}
            </View>
          )}

          {/* Report */}
          {report ? (
            <View style={st.reportCard}>
              <Text style={st.reportTitle}>{report.report_title || 'Breakthrough Report'}</Text>
              {report.breakthrough_score && (
                <View style={st.scoreBadge}>
                  <Text style={st.scoreText}>Breakthrough Score: {report.breakthrough_score}/10</Text>
                </View>
              )}
              {report.sections?.map((sec: any, i: number) => (
                <View key={i} style={st.reportSection}>
                  <Text style={st.sectionTitle}>{sec.title}</Text>
                  <Text style={st.sectionContent}>{sec.content}</Text>
                </View>
              ))}
            </View>
          ) : hasContent ? (
            <TouchableOpacity style={st.generateBtn} onPress={handleGenerateReport} disabled={generatingReport}>
              {generatingReport ? (
                <><ActivityIndicator color="#FFF" /><Text style={st.generateBtnText}>Generating Report...</Text></>
              ) : (
                <><Ionicons name="sparkles" size={18} color="#FFF" /><Text style={st.generateBtnText}>Generate AI Breakthrough Report{reportEst ? ` · ~${reportEst} cr` : ''}</Text></>
              )}
            </TouchableOpacity>
          ) : null}

          {/* Commitments */}
          <View style={st.sectionHeader}>
            <Text style={st.sectionHeaderTitle}>Commitments</Text>
            <TouchableOpacity onPress={() => setShowCommit(!showCommit)}>
              <Ionicons name={showCommit ? 'close' : 'add-circle'} size={24} color="#F59E0B" />
            </TouchableOpacity>
          </View>
          {showCommit && (
            <View style={st.commitForm}>
              <TextInput style={st.input} placeholder="What will you commit to?"
                value={commitText} onChangeText={setCommitText} placeholderTextColor={COLORS.textMuted} />
              <View style={st.commitTypes}>
                {['immediate', '7_day', '30_day'].map(t => (
                  <TouchableOpacity key={t} style={[st.commitTypeBtn, commitType === t && st.commitTypeBtnActive]}
                    onPress={() => setCommitType(t)}>
                    <Text style={[st.commitTypeText, commitType === t && st.commitTypeTextActive]}>
                      {t.replace('_', ' ')}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <TouchableOpacity style={st.saveBtn} onPress={handleAddCommitment} disabled={savingCommit}>
                {savingCommit ? <ActivityIndicator color="#FFF" /> :
                  <Text style={st.saveBtnText}>Add Commitment</Text>}
              </TouchableOpacity>
            </View>
          )}
          {session.commitments?.map((c: any) => (
            <View key={c.id} style={st.commitCard}>
              <TouchableOpacity
                style={[st.commitCheck, c.status === 'completed' && st.commitCheckDone]}
                onPress={() => c.status !== 'completed' && handleCompleteCommitment(c.id)}>
                {c.status === 'completed' && <Ionicons name="checkmark" size={14} color="#FFF" />}
              </TouchableOpacity>
              <View style={{ flex: 1 }}>
                <Text style={[st.commitText, c.status === 'completed' && st.commitTextDone]}>{c.commitment_text}</Text>
                <Text style={st.commitMeta}>{c.commitment_type.replace('_', ' ')} • {c.status}</Text>
              </View>
            </View>
          ))}

          {/* Journal */}
          <View style={st.sectionHeader}>
            <Text style={st.sectionHeaderTitle}>Journal</Text>
            <TouchableOpacity onPress={() => setShowJournal(!showJournal)}>
              <Ionicons name={showJournal ? 'close' : 'create'} size={24} color="#F59E0B" />
            </TouchableOpacity>
          </View>
          {showJournal && (
            <View style={st.journalForm}>
              <TextInput style={[st.input, { minHeight: 100, textAlignVertical: 'top' }]} multiline
                placeholder="Write your reflections..." value={journalContent}
                onChangeText={setJournalContent} placeholderTextColor={COLORS.textMuted} />
              <TouchableOpacity style={st.saveBtn} onPress={handleSaveJournal} disabled={savingJournal}>
                {savingJournal ? <ActivityIndicator color="#FFF" /> :
                  <Text style={st.saveBtnText}>Save Journal Entry</Text>}
              </TouchableOpacity>
            </View>
          )}
          {session.journal && (
            <View style={st.journalCard}>
              <Ionicons name="book" size={16} color="#D97706" />
              <Text style={st.journalText}>{session.journal.journal_content}</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { padding: 20, paddingTop: 8, borderBottomLeftRadius: 20, borderBottomRightRadius: 20 },
  headerTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  headerMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  typeBadge: { backgroundColor: 'rgba(255,255,255,0.3)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  typeBadgeText: { fontSize: 10, fontWeight: '700', color: '#FFF' },
  headerDate: { fontSize: 12, color: 'rgba(255,255,255,0.8)' },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 10, fontWeight: '700', color: '#FFF', textTransform: 'uppercase' },
  content: { padding: 16 },
  aiCostRow: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F5F3FF', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginBottom: 12, borderWidth: 1, borderColor: '#E9D5FF' },
  aiCostText: { fontSize: 12, fontWeight: '600', color: '#6D28D9' },
  intensityRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 20, backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  intensityItem: { alignItems: 'center' },
  intensityNum: { fontSize: 28, fontWeight: '800', color: COLORS.textPrimary },
  intensityLabel: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  reportCard: { backgroundColor: '#FFFBEB', borderRadius: 16, padding: 20, marginBottom: 16, borderWidth: 1, borderColor: '#FDE68A' },
  reportTitle: { fontSize: 18, fontWeight: '800', color: '#92400E', marginBottom: 8 },
  scoreBadge: { backgroundColor: '#D97706', alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, marginBottom: 12 },
  scoreText: { fontSize: 12, fontWeight: '700', color: '#FFF' },
  reportSection: { marginBottom: 12 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#92400E', marginBottom: 4 },
  sectionContent: { fontSize: 13, color: '#78350F', lineHeight: 19 },
  generateBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#F59E0B', borderRadius: 14, paddingVertical: 16, marginBottom: 16 },
  generateBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, marginBottom: 8 },
  sectionHeaderTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  commitForm: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: '#FDE68A' },
  input: { backgroundColor: '#F9FAFB', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  commitTypes: { flexDirection: 'row', gap: 8, marginTop: 10 },
  commitTypeBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: '#F3F4F6', alignItems: 'center' },
  commitTypeBtnActive: { backgroundColor: '#F59E0B' },
  commitTypeText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  commitTypeTextActive: { color: '#FFF' },
  saveBtn: { backgroundColor: '#F59E0B', borderRadius: 10, paddingVertical: 12, alignItems: 'center', marginTop: 10 },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  commitCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: COLORS.border },
  commitCheck: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  commitCheckDone: { backgroundColor: '#10B981', borderColor: '#10B981' },
  commitText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  commitTextDone: { textDecorationLine: 'line-through', color: COLORS.textMuted },
  commitMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  journalForm: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: '#FDE68A' },
  journalCard: { flexDirection: 'row', gap: 8, backgroundColor: '#FFFBEB', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#FDE68A' },
  journalText: { fontSize: 13, color: '#78350F', flex: 1, lineHeight: 18 },
  insightCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  insightTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 6 },
  stageBadge: { alignSelf: 'flex-start', backgroundColor: '#D97706', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 5, marginTop: 4, marginBottom: 4 },
  stageText: { fontSize: 11, fontWeight: '700', color: '#FFF' },
  aLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 12 },
  aText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginTop: 3 },
  oldBelief: { fontSize: 13, color: '#DC2626', textDecorationLine: 'line-through', lineHeight: 19, marginTop: 3 },
  highlightBox: { flexDirection: 'row', gap: 8, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12, marginTop: 12 },
  highlightText: { flex: 1, fontSize: 13, color: '#5B21B6', lineHeight: 19, fontWeight: '600' },
  greenBox: { flexDirection: 'row', gap: 8, backgroundColor: '#ECFDF5', borderRadius: 10, padding: 12, marginTop: 8 },
  greenText: { flex: 1, fontSize: 13, color: '#065F46', lineHeight: 19 },
  amberBox: { flexDirection: 'row', gap: 8, backgroundColor: '#FFFBEB', borderRadius: 10, padding: 12, marginTop: 8 },
  amberText: { flex: 1, fontSize: 13, color: '#92400E', lineHeight: 19 },
  affirm: { fontStyle: 'italic', textAlign: 'center', color: COLORS.primary, fontSize: 13, marginTop: 14, fontWeight: '600', lineHeight: 19 },
  subItem: { marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border },
  subHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  subName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  emptyCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 28, marginTop: 8, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  emptyTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, marginTop: 12 },
  emptySub: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginTop: 8, lineHeight: 19 },
  resumeBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F59E0B', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 24, marginTop: 18 },
  resumeBtnText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
});
