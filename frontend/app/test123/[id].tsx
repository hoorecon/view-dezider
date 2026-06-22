import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';

interface Test123Session {
  id: string;
  situation: string;
  is_emotional: boolean | null;
  what_i_want: string;
  worst_case_scenario: string;
  ready_for_worst: boolean | null;
  all_needs: string[];
  important_needs: string[];
  action_plan: string;
  final_decision: string;
  completed_test: number;
}

export default function Test123Detail() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const [session, setSession] = useState<Test123Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentTest, setCurrentTest] = useState(1);

  // Form states
  const [whatIWant, setWhatIWant] = useState('');
  const [worstCase, setWorstCase] = useState('');
  const [newNeed, setNewNeed] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [actionPlan, setActionPlan] = useState('');
  const [finalDecision, setFinalDecision] = useState('');
  const [showRiskGate, setShowRiskGate] = useState(false);

  useEffect(() => {
    fetchSession();
  }, [id]);

  const fetchSession = async () => {
    try {
      const response = await api.get(`/test123/${id}`);
      setSession(response.data);
      setWhatIWant(response.data.what_i_want || '');
      setWorstCase(response.data.worst_case_scenario || '');
      setActionPlan(response.data.action_plan || '');
      setFinalDecision(response.data.final_decision || '');
      
      // Set current test based on progress
      if (response.data.completed_test >= 3) {
        setCurrentTest(4); // Complete view
      } else {
        setCurrentTest(response.data.completed_test + 1);
      }
    } catch (error) {
      showAlert('Error', 'Failed to load session');
      router.back();
    } finally {
      setLoading(false);
    }
  };

  const saveSession = async (updates: Partial<Test123Session>) => {
    setSaving(true);
    try {
      await api.put(`/test123/${id}`, updates);
      setSession({ ...session!, ...updates });
    } catch (error) {
      showAlert('Error', 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const handleEmotionalResponse = async (isEmotional: boolean) => {
    await saveSession({ is_emotional: isEmotional });
    if (!isEmotional) {
      // If not emotional, can proceed directly
      setCurrentTest(1.5); // Show "What do I want" question
    } else {
      // If emotional, show Test 2
      setCurrentTest(2);
    }
  };

  const handleWhatIWant = async () => {
    if (!whatIWant.trim()) {
      showAlert('Error', 'Please describe what you want');
      return;
    }
    await saveSession({ what_i_want: whatIWant, completed_test: 1 });
    if (!session?.is_emotional) {
      // If not emotional, decision is made
      setFinalDecision(whatIWant);
      setCurrentTest(4);
      await saveSession({ final_decision: whatIWant, completed_test: 3 });
    } else {
      setCurrentTest(2);
    }
  };

  const handleWorstCase = async () => {
    if (!worstCase.trim()) {
      showAlert('Error', 'Please describe the worst case scenario');
      return;
    }
    await saveSession({ worst_case_scenario: worstCase });
  };

  const handleReadyForWorst = async (ready: boolean) => {
    await saveSession({ ready_for_worst: ready, completed_test: 2 });
    if (ready) {
      // If ready for worst, proceed with emotional decision
      setCurrentTest(4);
      await saveSession({ final_decision: whatIWant || 'Proceed with emotional response', completed_test: 3 });
    } else {
      // If not ready, go to Test 3
      setCurrentTest(3);
    }
  };

  const addNeed = () => {
    if (!newNeed.trim()) return;
    const updatedNeeds = [...(session?.all_needs || []), newNeed.trim()];
    saveSession({ all_needs: updatedNeeds });
    setNewNeed('');
  };

  const startEditNeed = (index: number, current: string) => {
    setEditingIndex(index);
    setEditingText(current);
  };

  const commitEditNeed = () => {
    if (editingIndex === null || !session) return;
    const trimmed = editingText.trim();
    if (!trimmed) {
      // Empty value cancels the edit
      setEditingIndex(null);
      setEditingText('');
      return;
    }
    const oldVal = session.all_needs[editingIndex];
    const updatedNeeds = session.all_needs.map((n, i) => (i === editingIndex ? trimmed : n));
    // Keep the "important" flag intact for the renamed entry
    const updatedImportant = session.important_needs.map((n) => (n === oldVal ? trimmed : n));
    saveSession({ all_needs: updatedNeeds, important_needs: updatedImportant });
    setEditingIndex(null);
    setEditingText('');
  };

  const cancelEditNeed = () => {
    setEditingIndex(null);
    setEditingText('');
  };

  const removeNeed = (index: number) => {
    const updatedNeeds = session!.all_needs.filter((_, i) => i !== index);
    const updatedImportant = session!.important_needs.filter(
      (need) => updatedNeeds.includes(need)
    );
    saveSession({ all_needs: updatedNeeds, important_needs: updatedImportant });
    if (editingIndex === index) cancelEditNeed();
  };

  const toggleImportantNeed = (need: string) => {
    const isImportant = session?.important_needs.includes(need);
    const updatedImportant = isImportant
      ? session!.important_needs.filter((n) => n !== need)
      : [...(session?.important_needs || []), need];
    saveSession({ important_needs: updatedImportant });
  };

  const handleFinalDecision = async () => {
    if (!actionPlan.trim() || !finalDecision.trim()) {
      showAlert('Error', 'Please fill in your action plan and final decision');
      return;
    }
    await saveSession({
      action_plan: actionPlan,
      final_decision: finalDecision,
      completed_test: 3,
    });
    setCurrentTest(4);
  };

  if (loading || !session) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.accent} />
        </View>
      </SafeAreaView>
    );
  }

  const renderTest1 = () => (
    <View style={styles.testContent}>
      <View style={styles.testHeader}>
        <View style={[styles.testBadge, { backgroundColor: COLORS.accent }]}>
          <Text style={styles.testBadgeText}>Test 1</Text>
        </View>
        {saving && <ActivityIndicator size="small" color={COLORS.accent} />}
      </View>

      <Text style={styles.testQuestion}>Am I emotional right now?</Text>
      <Text style={styles.testDescription}>
        Before making any decision, honestly assess if your emotions (anger, fear, excitement, sadness) are influencing your thinking.
      </Text>

      <Card style={styles.situationCard}>
        <Text style={styles.situationLabel}>Your Situation:</Text>
        <Text style={styles.situationText}>{session.situation}</Text>
      </Card>

      <View style={styles.yesNoButtons}>
        <TouchableOpacity
          style={[styles.yesNoButton, styles.yesButton]}
          onPress={() => handleEmotionalResponse(true)}
        >
          <Ionicons name="heart" size={24} color={COLORS.white} />
          <Text style={styles.yesNoText}>Yes, I'm emotional</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.yesNoButton, styles.noButton]}
          onPress={() => handleEmotionalResponse(false)}
        >
          <Ionicons name="analytics" size={24} color={COLORS.white} />
          <Text style={styles.yesNoText}>No, I'm calm</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderWhatIWant = () => (
    <View style={styles.testContent}>
      <View style={styles.testHeader}>
        <View style={[styles.testBadge, { backgroundColor: COLORS.success }]}>
          <Text style={styles.testBadgeText}>Focus</Text>
        </View>
      </View>

      <Text style={styles.testQuestion}>What do I really want?</Text>
      <Text style={styles.testDescription}>
        Since you're thinking clearly, focus on your true objective. What outcome do you actually want from this situation?
      </Text>

      <Input
        placeholder="Describe what you truly want..."
        value={whatIWant}
        onChangeText={setWhatIWant}
        multiline
        numberOfLines={4}
      />

      <GradientButton
        title="This is my decision"
        onPress={handleWhatIWant}
        variant="accent"
        style={styles.actionButton}
      />
    </View>
  );

  const renderTest2 = () => (
    <View style={styles.testContent}>
      <View style={styles.testHeader}>
        <View style={[styles.testBadge, { backgroundColor: COLORS.warning }]}>
          <Text style={styles.testBadgeText}>Test 2</Text>
        </View>
        {saving && <ActivityIndicator size="small" color={COLORS.warning} />}
      </View>

      <Text style={styles.testQuestion}>What's the worst that can happen?</Text>
      <Text style={styles.testDescription}>
        You acknowledged being emotional. Before reacting, consider: what's the worst possible outcome if you act on these emotions?
      </Text>

      <Input
        placeholder="Describe the worst case scenario..."
        value={worstCase}
        onChangeText={setWorstCase}
        multiline
        numberOfLines={3}
      />

      {worstCase.trim() && (
        <>
          <Text style={styles.followUpQuestion}>Am I ready to face this worst case?</Text>

          <View style={styles.yesNoButtons}>
            <TouchableOpacity
              style={[styles.yesNoButton, styles.yesButton]}
              onPress={() => {
                handleWorstCase();
                handleReadyForWorst(true);
              }}
            >
              <Ionicons name="checkmark-circle" size={24} color={COLORS.white} />
              <Text style={styles.yesNoText}>Yes, I can face this worst case</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.yesNoButton, styles.noButton]}
              onPress={() => {
                handleWorstCase();
                saveSession({ ready_for_worst: false, completed_test: 2 });
                setShowRiskGate(true);
              }}
            >
              <Ionicons name="close-circle" size={24} color={COLORS.white} />
              <Text style={styles.yesNoText}>No, its too risky</Text>
            </TouchableOpacity>
          </View>
        </>
      )}
    </View>
  );

  const renderTest3 = () => (
    <View style={styles.testContent}>
      <View style={styles.testHeader}>
        <View style={[styles.testBadge, { backgroundColor: COLORS.success }]}>
          <Text style={styles.testBadgeText}>Test 3</Text>
        </View>
        {saving && <ActivityIndicator size="small" color={COLORS.success} />}
      </View>

      <Text style={styles.testQuestion}>What do I truly need?</Text>
      <Text style={styles.testDescription}>
        List all your needs in this situation, then identify the most important ones. Focus on getting at least these for sure.
      </Text>

      <View style={styles.needsSection}>
        <Text style={styles.sectionLabel}>All My Needs:</Text>
        <Text style={styles.helperText}>
          Tap ⭐ to mark a need as "Most Important", ✎ to edit, ✕ to remove.
        </Text>
        {session.all_needs.map((need, index) => {
          const isEditing = editingIndex === index;
          const isImportant = session.important_needs.includes(need);
          return (
            <Card key={index} style={styles.needCard}>
              <View style={styles.needRow}>
                <TouchableOpacity onPress={() => toggleImportantNeed(need)} hitSlop={8}>
                  <Ionicons
                    name={isImportant ? 'star' : 'star-outline'}
                    size={20}
                    color={isImportant ? COLORS.warning : COLORS.textMuted}
                  />
                </TouchableOpacity>

                {isEditing ? (
                  <TextInput
                    style={styles.needEditInput}
                    value={editingText}
                    onChangeText={setEditingText}
                    autoFocus
                    onSubmitEditing={commitEditNeed}
                    placeholder="Need..."
                    placeholderTextColor={COLORS.textMuted}
                  />
                ) : (
                  <TouchableOpacity style={styles.needTextWrap} onPress={() => toggleImportantNeed(need)}>
                    <Text style={styles.needText}>{need}</Text>
                  </TouchableOpacity>
                )}

                {isEditing ? (
                  <>
                    <TouchableOpacity onPress={commitEditNeed} hitSlop={8} style={styles.editActionBtn}>
                      <Ionicons name="checkmark" size={20} color={COLORS.success || '#16A34A'} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={cancelEditNeed} hitSlop={8} style={styles.editActionBtn}>
                      <Ionicons name="close" size={20} color={COLORS.textMuted} />
                    </TouchableOpacity>
                  </>
                ) : (
                  <>
                    <TouchableOpacity onPress={() => startEditNeed(index, need)} hitSlop={8} style={styles.editActionBtn} accessibilityLabel="Edit need">
                      <Ionicons name="pencil" size={18} color={COLORS.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => removeNeed(index)} hitSlop={8} style={styles.editActionBtn} accessibilityLabel="Remove need">
                      <Ionicons name="close" size={20} color={COLORS.error} />
                    </TouchableOpacity>
                  </>
                )}
              </View>
            </Card>
          );
        })}

        <View style={styles.addNeedRow}>
          <TextInput
            style={styles.addNeedInput}
            placeholder="Add a need..."
            placeholderTextColor={COLORS.textMuted}
            value={newNeed}
            onChangeText={setNewNeed}
            onSubmitEditing={addNeed}
          />
          <TouchableOpacity style={styles.addNeedButton} onPress={addNeed}>
            <Ionicons name="add" size={24} color={COLORS.white} />
          </TouchableOpacity>
        </View>

        {/* Always render the "Most Important" section so users see it as
            a clear next step even before they tap any star. */}
        <View style={styles.importantSection}>
          <Text style={styles.importantLabel}>
            Most Important Needs{session.important_needs.length > 0 ? ` (${session.important_needs.length} selected)` : ''}:
          </Text>
          {session.important_needs.length > 0 ? (
            <Text style={styles.importantNeeds}>
              {session.important_needs.join(', ')}
            </Text>
          ) : (
            <Text style={styles.importantHint}>
              Tap the ⭐ next to any need above to mark it as critical. These are
              the ones you must secure even if everything else is compromised.
            </Text>
          )}
        </View>
      </View>

      <Input
        label="Action Plan"
        placeholder="What can I do to get at least my most important needs?"
        value={actionPlan}
        onChangeText={setActionPlan}
        multiline
        numberOfLines={3}
      />

      <Input
        label="My Final Decision"
        placeholder="Based on this analysis, my decision is..."
        value={finalDecision}
        onChangeText={setFinalDecision}
        multiline
        numberOfLines={2}
      />

      <GradientButton
        title="Complete Decision"
        onPress={handleFinalDecision}
        variant="accent"
        style={styles.actionButton}
        disabled={!actionPlan.trim() || !finalDecision.trim()}
      />
    </View>
  );

  const renderComplete = () => {
    const emotionalAnswer = session.is_emotional === true
      ? 'Yes — I was emotional'
      : session.is_emotional === false
        ? 'No — I was calm'
        : null;
    const worstCaseAnswer = session.ready_for_worst === true
      ? 'Yes — I can face this worst case'
      : session.ready_for_worst === false
        ? 'No, its too risky'
        : null;

    return (
      <View style={styles.testContent}>
        <View style={styles.completeHeader}>
          <Ionicons name="checkmark-circle" size={64} color={COLORS.success} />
          <Text style={styles.completeTitle}>Decision Made!</Text>
        </View>

        <Card style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Situation:</Text>
          <Text style={styles.summaryText}>{session.situation}</Text>
        </Card>

        {/* Step 1 Q&A — Emotional Check */}
        {emotionalAnswer && (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryQ}>Am I emotional right now?</Text>
            <Text style={styles.summaryA}>{emotionalAnswer}</Text>
          </Card>
        )}

        {/* Step 1.5 Q&A — Focus / What I Really Want */}
        {session.what_i_want ? (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryQ}>What do I really want?</Text>
            <Text style={styles.summaryA}>{session.what_i_want}</Text>
          </Card>
        ) : null}

        {/* Step 2 Q&A — Worst Case Scenario */}
        {session.worst_case_scenario ? (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryQ}>What's the worst that could happen?</Text>
            <Text style={styles.summaryA}>{session.worst_case_scenario}</Text>
          </Card>
        ) : null}
        {worstCaseAnswer && (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryQ}>Can I face this worst case?</Text>
            <Text style={styles.summaryA}>{worstCaseAnswer}</Text>
          </Card>
        )}

        {/* Step 3 — Needs (all + important) */}
        {session.all_needs && session.all_needs.length > 0 ? (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryQ}>What are all my needs in this situation?</Text>
            {session.all_needs.map((n, i) => {
              const isImportant = session.important_needs?.includes(n);
              return (
                <View key={`need-${i}`} style={styles.needSummaryRow}>
                  <Ionicons
                    name={isImportant ? 'star' : 'ellipse-outline'}
                    size={14}
                    color={isImportant ? COLORS.warning : COLORS.textMuted}
                  />
                  <Text style={[styles.needSummaryText, isImportant && { fontWeight: '700', color: COLORS.textPrimary }]}>
                    {n}
                  </Text>
                </View>
              );
            })}
            {session.important_needs && session.important_needs.length > 0 ? (
              <Text style={styles.summaryHint}>
                ⭐ {session.important_needs.length} marked as most important — must be secured.
              </Text>
            ) : null}
          </Card>
        ) : null}

        {session.action_plan ? (
          <Card style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Action Plan:</Text>
            <Text style={styles.summaryText}>{session.action_plan}</Text>
          </Card>
        ) : null}

        <Card style={[styles.summaryCard, styles.decisionCard]}>
          <Text style={styles.decisionLabel}>Final Decision:</Text>
          <Text style={styles.decisionText}>{session.final_decision}</Text>
        </Card>

        <GradientButton
          title="Done"
          onPress={() => router.back()}
          style={styles.actionButton}
        />
      </View>
    );
  };

  const renderCurrentTest = () => {
    if (currentTest === 4) return renderComplete();
    if (currentTest === 3) return renderTest3();
    if (currentTest === 2) return renderTest2();
    if (currentTest === 1.5) return renderWhatIWant();
    return renderTest1();
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Explicit Back / Home toolbar — Stack default header's tint is
            barely visible on this screen's white BG, so render a clear
            high-contrast pair here. */}
        <View style={styles.topBar}>
          <TouchableOpacity
            style={styles.topBarBtn}
            onPress={() => router.back()}
            accessibilityLabel="Back"
            hitSlop={8}
          >
            <Ionicons name="arrow-back" size={20} color={COLORS.textPrimary} />
            <Text style={styles.topBarBtnText}>Back</Text>
          </TouchableOpacity>
          <View style={{ flex: 1 }} />
          <TouchableOpacity
            style={styles.topBarBtnSolid}
            onPress={() => router.push('/' as any)}
            accessibilityLabel="Home"
            hitSlop={8}
          >
            <Ionicons name="home" size={18} color={COLORS.white} />
          </TouchableOpacity>
        </View>

        {/* Progress indicator — tap a completed/touched step to jump back
            and edit. The current step stays highlighted; you cannot
            skip ahead. */}
        <View style={styles.progressContainer}>
          {[1, 2, 3].map((test) => {
            const reached = session.completed_test >= test || currentTest > test;
            const isCurrent = Math.ceil(currentTest) === test;
            const canJump = reached || isCurrent;
            return (
              <TouchableOpacity
                key={test}
                disabled={!canJump}
                onPress={() => canJump && setCurrentTest(test)}
                hitSlop={10}
                style={[
                  styles.progressDot,
                  reached && styles.progressDotComplete,
                  isCurrent && styles.progressDotCurrent,
                  canJump && !isCurrent && styles.progressDotEditable,
                ]}
                accessibilityLabel={`Step ${test}${canJump ? ' (tap to edit)' : ''}`}
              >
                {session.completed_test >= test ? (
                  <Ionicons name="checkmark" size={14} color={COLORS.white} />
                ) : (
                  <Text style={styles.progressText}>{test}</Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>

        {renderCurrentTest()}
      </ScrollView>

      <Modal visible={showRiskGate} transparent animationType="fade" onRequestClose={() => setShowRiskGate(false)}>
        <View style={styles.gateBackdrop}>
          <View style={styles.gateCard} testID="id-risk-gate">
            <Text style={styles.gateTitle}>Take a breath before deciding</Text>
            <Text style={styles.gateSub}>
              This feels risky right now. Would you like to keep exploring what you really
              need, or settle your emotions first? You can come right back here.
            </Text>
            <TouchableOpacity
              style={styles.gatePrimary}
              testID="id-gate-introspect"
              onPress={() => { setShowRiskGate(false); setCurrentTest(3); }}
            >
              <Ionicons name="bulb" size={16} color={COLORS.white} />
              <Text style={styles.gatePrimaryText}>Continue — explore what I really need</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.gateSecondary}
              testID="id-gate-reception"
              onPress={() => { setShowRiskGate(false); router.push(`/tools/eg-emotional-reception?return_to=test123&return_id=${id}` as any); }}
            >
              <Ionicons name="water" size={16} color="#0369A1" />
              <Text style={styles.gateSecondaryText}>Settle with Emotional Reception</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.gateSecondary}
              testID="id-gate-eft"
              onPress={() => { setShowRiskGate(false); router.push(`/tools/eg-eft?return_to=test123&return_id=${id}` as any); }}
            >
              <Ionicons name="hand-left" size={16} color="#0369A1" />
              <Text style={styles.gateSecondaryText}>Try EFT Tapping for Stress Relief</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  gateBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  gateCard: { backgroundColor: COLORS.white, borderRadius: 18, padding: 22 },
  gateTitle: { fontSize: 19, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 8 },
  gateSub: { fontSize: 14, color: COLORS.textSecondary, lineHeight: 21, marginBottom: 18 },
  gatePrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', paddingVertical: 14, borderRadius: 12, marginBottom: 10 },
  gatePrimaryText: { color: COLORS.white, fontSize: 15, fontWeight: '700' },
  gateSecondary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#E0F2FE', paddingVertical: 13, borderRadius: 12, marginBottom: 10 },
  gateSecondaryText: { color: '#0369A1', fontSize: 14, fontWeight: '700' },
  // ── Top navigation toolbar (explicit Back / Home) ──────────────
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingVertical: 4,
    marginBottom: 6,
    gap: 8,
  },
  topBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  topBarBtnText: {
    color: COLORS.textPrimary,
    fontSize: 13,
    fontWeight: '700',
  },
  topBarBtnSolid: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.primary,
  },

  // ── Summary Q&A styles ─────────────────────────────────────────
  summaryQ: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.primary,
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  summaryA: {
    fontSize: 14,
    color: COLORS.textPrimary,
    lineHeight: 20,
  },
  summaryHint: {
    fontSize: 11,
    color: COLORS.warning,
    marginTop: 6,
    fontStyle: 'italic',
  },
  needSummaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 3,
  },
  needSummaryText: {
    flex: 1,
    fontSize: 13,
    color: COLORS.textSecondary,
  },

  // ── Editable progress dot affordance ───────────────────────────
  progressDotEditable: {
    borderWidth: 2,
    borderColor: COLORS.primary,
  },
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    padding: 16,
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
    marginBottom: 24,
  },
  progressDot: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  progressDotComplete: {
    backgroundColor: COLORS.success,
  },
  progressDotCurrent: {
    borderWidth: 3,
    borderColor: COLORS.accent,
  },
  progressText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  testContent: {
    flex: 1,
  },
  testHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  testBadge: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 16,
  },
  testBadgeText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  testQuestion: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  testDescription: {
    fontSize: 15,
    color: COLORS.textSecondary,
    lineHeight: 22,
    marginBottom: 24,
  },
  situationCard: {
    marginBottom: 24,
    backgroundColor: COLORS.white,
  },
  situationLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 4,
  },
  situationText: {
    fontSize: 15,
    color: COLORS.textPrimary,
    lineHeight: 22,
  },
  yesNoButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  yesNoButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  yesButton: {
    backgroundColor: COLORS.accent,
  },
  noButton: {
    backgroundColor: COLORS.teal,
  },
  yesNoText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.white,
  },
  followUpQuestion: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 24,
    marginBottom: 16,
    textAlign: 'center',
  },
  actionButton: {
    marginTop: 16,
    marginBottom: 32,
  },
  needsSection: {
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  needCard: {
    marginBottom: 8,
    padding: 12,
  },
  needRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  needText: {
    flex: 1,
    fontSize: 14,
    color: COLORS.textPrimary,
  },
  addNeedRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  addNeedInput: {
    flex: 1,
    height: 44,
    backgroundColor: COLORS.white,
    borderRadius: 10,
    paddingHorizontal: 14,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  addNeedButton: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  importantSection: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
  },
  importantLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.warning,
    marginBottom: 4,
  },
  importantNeeds: {
    fontSize: 14,
    color: COLORS.textPrimary,
  },
  importantHint: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
    lineHeight: 17,
  },
  helperText: {
    fontSize: 11,
    color: COLORS.textMuted,
    marginBottom: 8,
    marginTop: -4,
  },
  needTextWrap: {
    flex: 1,
  },
  needEditInput: {
    flex: 1,
    height: 36,
    backgroundColor: COLORS.white,
    borderRadius: 8,
    paddingHorizontal: 10,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  editActionBtn: {
    paddingHorizontal: 4,
    paddingVertical: 4,
  },
  completeHeader: {
    alignItems: 'center',
    marginBottom: 24,
  },
  completeTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.success,
    marginTop: 12,
  },
  summaryCard: {
    marginBottom: 12,
  },
  summaryLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 4,
  },
  summaryText: {
    fontSize: 14,
    color: COLORS.textPrimary,
    lineHeight: 20,
  },
  decisionCard: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderWidth: 1,
    borderColor: COLORS.success,
  },
  decisionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.success,
    marginBottom: 4,
  },
  decisionText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    lineHeight: 22,
  },
});
