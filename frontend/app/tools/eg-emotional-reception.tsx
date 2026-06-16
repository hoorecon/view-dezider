import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
  Animated, Easing, Modal, Pressable,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useLocalSearchParams } from 'expo-router';
import VentToOutletsBanner from '../../src/components/VentToOutletsBanner';
import { Alert } from '../../src/utils/crossAlert';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { VoiceTextInput } from '../../src/components/VoiceTextInput';
import { ConfirmDialog } from '../../src/components/ConfirmDialog';
import api from '../../src/utils/api';

const DONTS = [
  {
    num: 1,
    dont: "LET'S NOT EXPRESS OUR ANGER",
    detail: "by any Action or Words or even by Thoughts — internally.\nHowever, we can BE in the feeling of ANGER.",
    icon: 'flame',
  },
  {
    num: 2,
    dont: "LET'S NOT EXPRESS OUR SADNESS",
    detail: "by any Action or Words or even by Thoughts — internally.\nHowever, we can BE in the feeling of SADNESS.",
    icon: 'water',
  },
  {
    num: 3,
    dont: "LET'S NOT DEVIATE",
    detail: "from the pain of this moment with any of our usual Habits of Deviations (like talking to a friend or mom, reading, TV, games) or addictions (like Cigar, Alcohol etc.).",
    icon: 'git-branch',
  },
  {
    num: 4,
    dont: "LET'S NOT ANALYZE",
    detail: "for any Solutions to the current challenge, just for the next 5 mins.",
    icon: 'analytics',
  },
  {
    num: 5,
    dont: "LET'S NOT TAKE any Action",
    detail: "to resolve this challenge.",
    icon: 'hand-left',
  },
  {
    num: 6,
    dont: "LET'S NOT SLEEP also.",
    detail: "Stay awake and present with your feeling.",
    icon: 'moon',
  },
  {
    num: 7,
    dont: "LET'S NOT TRY TO MEDITATE",
    detail: "or APPLY any prior-known techniques to handle the pain.",
    icon: 'fitness',
  },
];

const TIMER_DURATION = 300; // 5 minutes

export default function EmotionalReceptionScreen() {
  const params = useLocalSearchParams<{ return_to?: string; return_id?: string }>();
  const router = useRouter();
  const goBack = () => {
    if (params.return_to === 'solution-finder' && params.return_id) {
      router.replace(`/tools/solution-finder?id=${params.return_id}&step=2` as any);
      return;
    }
    if (router.canGoBack?.()) router.back();
    else router.replace('/tools/emotional-gatekeeper' as any);
  };
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  // Step 0: Burden
  const [burden, setBurden] = useState('');
  const [intensityBefore, setIntensityBefore] = useState(5);

  // Step 1: Guidance & DON'Ts shown
  // Step 2: Choice — Yes I can wait / No I cannot
  const [choseToBe, setChoseToBe] = useState<boolean | null>(null);

  // Step 3: Timer (5 mins)
  const [timerActive, setTimerActive] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(TIMER_DURATION);
  const [timerCompleted, setTimerCompleted] = useState(false);
  // Themed in-app confirm dialog for the "I need to stop" abandon flow
  // (replaces the harsh `window.confirm` shown by browser-native Alert).
  const [showAbandonConfirm, setShowAbandonConfirm] = useState(false);
  const timerRef = useRef<any>(null);

  // Step 4: Completion
  const [intensityAfter, setIntensityAfter] = useState(3);
  const [reflection, setReflection] = useState('');
  const [eqStats, setEqStats] = useState<any>(null);
  const [showEqBreakdown, setShowEqBreakdown] = useState(false);

  // Animations
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const breatheAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (timerActive) {
      // Pulse animation during timer
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.08, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        ])
      );
      pulse.start();

      // Breathe indicator
      const breathe = Animated.loop(
        Animated.sequence([
          Animated.timing(breatheAnim, { toValue: 1, duration: 4000, useNativeDriver: false }),
          Animated.timing(breatheAnim, { toValue: 0, duration: 6000, useNativeDriver: false }),
        ])
      );
      breathe.start();

      return () => { pulse.stop(); breathe.stop(); };
    }
  }, [timerActive]);

  const startTimer = () => {
    setTimerActive(true);
    setTimerSeconds(TIMER_DURATION);
    timerRef.current = setInterval(() => {
      setTimerSeconds(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          setTimerActive(false);
          setTimerCompleted(true);
          setStep(4);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const abandonTimer = () => {
    setShowAbandonConfirm(true);
  };

  const confirmAbandon = () => {
    setShowAbandonConfirm(false);
    if (timerRef.current) clearInterval(timerRef.current);
    setTimerActive(false);
    setTimerCompleted(false);
    setStep(4);
  };

  const handleFinish = async () => {
    setLoading(true);
    try {
      const res = await api.post('/emotional-gatekeeper/advisor/emotional-reception/log', {
        burden,
        wants_settled: true,
        accepted_donts: true,
        chose_to_be: choseToBe,
        completed_5_min: timerCompleted,
        intensity_before: intensityBefore,
        intensity_after: intensityAfter,
        reflection: reflection || null,
      });
      setEqStats(res.data.eq_stats);
      setStep(5);
    } catch (err) {
      Alert.alert('Error', 'Failed to save. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const breatheColor = breatheAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(14,165,233,0.15)', 'rgba(14,165,233,0.35)'],
  });

  // ── Step 0: What burden? ──
  const renderStep0 = () => (
    <View style={s.stepContent}>
      <Text style={s.scriptQ}>What burdens are you carrying now?</Text>
      <Text style={s.scriptHint}>Acknowledge it honestly. No judgement.</Text>
      <VoiceTextInput
        inputStyle={s.textArea}
        multiline
        placeholder="What's weighing on your mind right now..."
        value={burden}
        onChangeText={setBurden}
        placeholderTextColor={COLORS.textMuted}
        sessionId=""
        field="burden"
        color="#0EA5E9"
        module="eg-generic"
      />
      <Text style={s.label}>How intense is this feeling? ({intensityBefore}/10)</Text>
      <View style={s.sliderRow}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
          <TouchableOpacity key={n} style={[s.sliderDot,
            n <= intensityBefore && { backgroundColor: n <= 3 ? '#10B981' : n <= 6 ? '#F59E0B' : '#EF4444' }]}
            onPress={() => setIntensityBefore(n)}>
            <Text style={[s.sliderNum, n <= intensityBefore && { color: '#FFF' }]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TouchableOpacity style={s.nextBtn} onPress={() => {
        if (!burden.trim()) { Alert.alert('Required', 'Share what burden you are carrying.'); return; }
        setStep(1);
      }}>
        <Text style={s.nextBtnText}>Yes, I want it settled</Text>
        <Ionicons name="arrow-forward" size={18} color="#FFF" />
      </TouchableOpacity>
    </View>
  );

  // ── Step 1: Guidance + 7 DON'Ts ──
  const renderStep1 = () => (
    <View style={s.stepContent}>
      <View style={s.guidanceCard}>
        <Text style={s.guidanceText}>
          First and foremost, <Text style={s.bold}>do not resist</Text> this current situation and multiply the tension.
        </Text>
        <Text style={[s.guidanceText, { marginTop: 12 }]}>
          <Text style={s.bold}>Nobody on earth</Text> can change the reality of this very moment. Let this be as it is, right now.
        </Text>
        <Text style={[s.guidanceText, { marginTop: 12 }]}>
          Remember, if we're against this moment, we're against the <Text style={s.bold}>whole Universe</Text> and multiplying our problem. Be wise and realize this inevitability.
        </Text>
      </View>

      <Text style={s.dontsTitle}>7 DON'Ts — Just for 5 Minutes</Text>
      <Text style={s.dontsSubtitle}>Try to BE with this feeling of PAIN, just for 5 minutes only.</Text>

      {DONTS.map(d => (
        <View key={d.num} style={s.dontCard}>
          <View style={s.dontNumBg}>
            <Text style={s.dontNumText}>{d.num}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.dontTitle}>{d.dont}</Text>
            <Text style={s.dontDetail}>{d.detail}</Text>
          </View>
        </View>
      ))}

      <View style={s.questionBox}>
        <Ionicons name="help-circle" size={22} color="#0EA5E9" />
        <Text style={s.questionText}>
          "Then, what to do?"{'\n\n'}
          Just, <Text style={s.bold}>let's Be with our pain</Text> — only for 5 minutes.
          After these 5 minutes, we can do whatever we want.{'\n\n'}
          <Text style={s.italic}>"Let me BE with my pain, at least for the next 5 minutes."</Text>
        </Text>
      </View>

      <Text style={s.choiceTitle}>Can you wait for 5 minutes?</Text>
      <View style={s.choiceRow}>
        <TouchableOpacity style={[s.choiceBtn, s.choiceBtnYes]} onPress={() => { setChoseToBe(true); setStep(3); startTimer(); }}>
          <Ionicons name="checkmark-circle" size={22} color="#FFF" />
          <Text style={s.choiceBtnText}>Yes, I can wait 5 mins</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.choiceBtn, s.choiceBtnNo]} onPress={() => { setChoseToBe(false); setStep(4); }}>
          <Ionicons name="close-circle" size={22} color="#FFF" />
          <Text style={s.choiceBtnText}>No, I can't right now</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  // ── Step 3: 5-Minute Timer ──
  const renderStep3 = () => (
    <View style={[s.stepContent, { alignItems: 'center', paddingTop: 40 }]}>
      <Text style={s.timerLabel}>Being with my pain...</Text>
      <Animated.View style={[s.timerCircle, { transform: [{ scale: pulseAnim }] }]}>
        <Animated.View style={[s.timerInnerCircle, { backgroundColor: breatheColor }]}>
          <Text style={s.timerText}>{formatTime(timerSeconds)}</Text>
          <Text style={s.timerSubtext}>remaining</Text>
        </Animated.View>
      </Animated.View>

      <Text style={s.timerMessage}>Just BE.</Text>
      <Text style={s.timerSubMessage}>
        No action. No escape. No analysis.{'\n'}
        Simply sit with this feeling.
      </Text>

      <View style={s.breatheGuide}>
        <Ionicons name="leaf" size={18} color="#0EA5E9" />
        <Text style={s.breatheText}>Breathe naturally. Let whatever comes, come.</Text>
      </View>

      <TouchableOpacity style={s.abandonBtn} onPress={abandonTimer}>
        <Text style={s.abandonText}>I need to stop</Text>
      </TouchableOpacity>
    </View>
  );

  // ── Step 4: Completion or Encouragement ──
  const renderStep4 = () => (
    <View style={s.stepContent}>
      {timerCompleted ? (
        <LinearGradient colors={['#ECFDF5', '#D1FAE5']} style={s.completionCard}>
          <View style={s.congratsEmoji}>
            <Text style={{ fontSize: 40 }}>🌟</Text>
          </View>
          <Text style={s.congratsTitle}>Congratulations!</Text>
          <Text style={s.congratsText}>
            It's not that everyone can BE with their pain without doing anything for 5 minutes.
            Your <Text style={s.bold}>inner stability has grown up dramatically</Text>. Kudos!
          </Text>
          <Text style={s.congratsSub}>Let us keep up this inner balance!</Text>
        </LinearGradient>
      ) : choseToBe === false ? (
        <LinearGradient colors={['#FEF3C7', '#FDE68A']} style={s.completionCard}>
          <View style={s.congratsEmoji}>
            <Text style={{ fontSize: 40 }}>🤗</Text>
          </View>
          <Text style={[s.congratsTitle, { color: '#92400E' }]}>It's OK</Text>
          <Text style={[s.congratsText, { color: '#78350F' }]}>
            It will take time and practice to achieve this inner balance.
            Remember, this is the measure of your <Text style={s.bold}>EQ (Emotional Quotient)</Text>.
          </Text>
          <Text style={[s.congratsSub, { color: '#92400E' }]}>
            You can also learn the experiential access to your own inner source of creation and stability from upcoming Training Programs.
          </Text>
          <View style={s.contactBox}>
            <Ionicons name="mail" size={16} color="#D97706" />
            <Text style={s.contactText}>workshops@hoorecon.com</Text>
          </View>
        </LinearGradient>
      ) : (
        <LinearGradient colors={['#FEF3C7', '#FDE68A']} style={s.completionCard}>
          <View style={s.congratsEmoji}>
            <Text style={{ fontSize: 40 }}>💪</Text>
          </View>
          <Text style={[s.congratsTitle, { color: '#92400E' }]}>Good Effort!</Text>
          <Text style={[s.congratsText, { color: '#78350F' }]}>
            You chose to BE but couldn't complete the full 5 minutes. That's progress! Each attempt builds your EQ.
          </Text>
        </LinearGradient>
      )}

      <Text style={s.label}>How intense is the feeling now? ({intensityAfter}/10)</Text>
      <View style={s.sliderRow}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
          <TouchableOpacity key={n} style={[s.sliderDot,
            n <= intensityAfter && { backgroundColor: n <= 3 ? '#10B981' : n <= 6 ? '#F59E0B' : '#EF4444' }]}
            onPress={() => setIntensityAfter(n)}>
            <Text style={[s.sliderNum, n <= intensityAfter && { color: '#FFF' }]}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {(intensityBefore - intensityAfter > 0) && (
        <View style={s.shiftBadge}>
          <Ionicons name="trending-down" size={16} color="#059669" />
          <Text style={s.shiftText}>Intensity dropped by {intensityBefore - intensityAfter} points</Text>
        </View>
      )}

      <Text style={s.label}>Any reflection? (optional)</Text>
      <VoiceTextInput
        inputStyle={[s.textArea, { minHeight: 60 }]}
        multiline
        placeholder="What did you notice during the practice..."
        value={reflection}
        onChangeText={setReflection}
        placeholderTextColor={COLORS.textMuted}
        sessionId=""
        field="reflection"
        color="#0EA5E9"
        module="eg-generic"
      />

      <TouchableOpacity style={s.nextBtn} onPress={handleFinish} disabled={loading}>
        {loading ? <ActivityIndicator color="#FFF" /> :
          <><Text style={s.nextBtnText}>Complete & Save</Text><Ionicons name="checkmark-circle" size={18} color="#FFF" /></>}
      </TouchableOpacity>
    </View>
  );

  // ── Step 5: EQ Summary ──
  const renderStep5 = () => (
    <View style={[s.stepContent, { alignItems: 'center' }]}>
      <LinearGradient colors={['#0EA5E9', '#0284C7']} style={s.eqCard}>
        <View style={s.eqTitleRow}>
          <Text style={s.eqTitle}>Your EQ Growth</Text>
          <TouchableOpacity
            onPress={() => setShowEqBreakdown(true)}
            hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}
            accessibilityRole="button"
            accessibilityLabel="How is this score calculated?"
          >
            <Ionicons name="information-circle-outline" size={22} color="rgba(255,255,255,0.85)" />
          </TouchableOpacity>
        </View>
        {eqStats && (
          <>
            <View style={s.eqRow}>
              <View style={s.eqItem}>
                <Text style={s.eqNum}>{eqStats.total_attempts}</Text>
                <Text style={s.eqLabel}>Total Attempts</Text>
              </View>
              <View style={s.eqDivider} />
              <View style={s.eqItem}>
                <Text style={s.eqNum}>{eqStats.successful_completions}</Text>
                <Text style={s.eqLabel}>Completions</Text>
              </View>
              <View style={s.eqDivider} />
              <View style={s.eqItem}>
                <Text style={s.eqNum}>{eqStats.eq_score}/10</Text>
                <Text style={s.eqLabel}>EQ Score</Text>
              </View>
            </View>
          </>
        )}
      </LinearGradient>

      <TouchableOpacity
        style={[s.nextBtn, { width: '100%' }]}
        onPress={() => router.push('/tools/eg-trap' as any)}
      >
        <Ionicons name="flash" size={18} color="#FFF" />
        <Text style={s.nextBtnText}>Breaking the Trap</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[s.secondaryBtn, { width: '100%' }]}
        onPress={() => router.push('/tools/eg-advisor' as any)}
      >
        <Ionicons name="leaf-outline" size={16} color="#0EA5E9" />
        <Text style={s.secondaryBtnText}>Effective Outlets Advisor</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={s.doneBtn}
        onPress={() => router.push('/tools/emotional-gatekeeper' as any)}
      >
        <Text style={s.doneBtnText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        {step !== 3 && (
          <LinearGradient colors={['#0EA5E9', '#0284C7', '#0369A1']} style={s.header}>
            <TouchableOpacity style={s.backBtn} onPress={() => {
              if (timerActive) { abandonTimer(); return; }
              goBack();
            }}>
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <Text style={s.headerTitle}>Emotional Reception</Text>
            <Text style={s.headerSub}>Just Be in the Here and Now</Text>
          </LinearGradient>
        )}
        {step === 3 ? (
          <LinearGradient colors={['#0C4A6E', '#0E7490', '#0EA5E9']} style={{ flex: 1, justifyContent: 'center' }}>
            {renderStep3()}
          </LinearGradient>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
            <VentToOutletsBanner returnTo={(params as any).return_to} returnId={(params as any).return_id} />
            {step === 0 && renderStep0()}
            {step === 1 && renderStep1()}
            {step === 4 && renderStep4()}
            {step === 5 && renderStep5()}
          </ScrollView>
        )}
      </KeyboardAvoidingView>
      <ConfirmDialog
        visible={showAbandonConfirm}
        theme="dark"
        title="Leave Practice?"
        message={"It's OK if you can't complete it this time.\nWould you like to stop?"}
        confirmLabel="Stop"
        cancelLabel="Continue"
        destructive
        onCancel={() => setShowAbandonConfirm(false)}
        onConfirm={confirmAbandon}
      />
      {/* EQ formula breakdown — opens from the (i) icon on the EQ card */}
      <Modal
        visible={showEqBreakdown}
        transparent
        animationType="fade"
        onRequestClose={() => setShowEqBreakdown(false)}
      >
        <Pressable style={s.eqInfoOverlay} onPress={() => setShowEqBreakdown(false)}>
          <Pressable style={s.eqInfoCard} onPress={(e) => e.stopPropagation()}>
            <View style={s.eqInfoHeaderRow}>
              <Text style={s.eqInfoTitle}>How EQ Score is calculated</Text>
              <TouchableOpacity onPress={() => setShowEqBreakdown(false)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>
            <Text style={s.eqInfoIntro}>
              Out of 10 — built from five reinforcing axes so daily practice
              earns more than one-off attempts.
            </Text>
            {eqStats?.eq_breakdown && (
              <View style={{ gap: 8 }}>
                <EqBreakdownRow label="Base" value={eqStats.eq_breakdown.base} cap={1.0} hint="Anyone who ever attempts starts here." />
                <EqBreakdownRow label="Completion bonus" value={eqStats.eq_breakdown.completion_bonus} cap={5.0} hint={`+0.5 per completed 5-min session · you have ${eqStats.successful_completions}`} />
                <EqBreakdownRow label="Attempt engagement" value={eqStats.eq_breakdown.attempt_engagement} cap={1.0} hint={`+0.1 per attempt (showing up matters) · you have ${eqStats.total_attempts}`} />
                <EqBreakdownRow label="Streak bonus" value={eqStats.eq_breakdown.streak_bonus} cap={2.0} hint={`+0.25 per consecutive day · current streak: ${eqStats.current_streak_days ?? 0} day(s)`} />
                <EqBreakdownRow label="Recent consistency (7d)" value={eqStats.eq_breakdown.recent_consistency_bonus} cap={1.0} hint={`+0.25 per completion in last 7 days · ${eqStats.completions_last_7d ?? 0} so far`} />
                <View style={s.eqInfoTotalRow}>
                  <Text style={s.eqInfoTotalLabel}>Total (capped at 10)</Text>
                  <Text style={s.eqInfoTotalValue}>{eqStats.eq_score}/10</Text>
                </View>
              </View>
            )}
            <Text style={s.eqInfoFooter}>
              Practicing daily — even short attempts — earns you 10/10 in about
              3 weeks. Lapses gradually reduce streak & recency components.
            </Text>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

/** Single-row renderer for the EQ breakdown modal. Kept inline to avoid a
 *  cross-file dependency for a screen-local UI affordance. */
function EqBreakdownRow({ label, value, cap, hint }: { label: string; value: number; cap: number; hint: string }) {
  const pct = Math.max(0, Math.min(1, value / cap));
  return (
    <View>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#0F172A' }}>{label}</Text>
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#0EA5E9' }}>{value.toFixed(2)} / {cap.toFixed(1)}</Text>
      </View>
      <View style={{ height: 6, borderRadius: 3, backgroundColor: '#E2E8F0', marginTop: 4, overflow: 'hidden' }}>
        <View style={{ width: `${pct * 100}%`, height: '100%', backgroundColor: '#0EA5E9' }} />
      </View>
      <Text style={{ fontSize: 11, color: '#64748B', marginTop: 3 }}>{hint}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { padding: 20, paddingTop: 8, borderBottomLeftRadius: 20, borderBottomRightRadius: 20 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2, fontStyle: 'italic' },
  stepContent: { padding: 16 },
  scriptQ: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 6 },
  scriptHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 16 },
  label: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 14, marginBottom: 8 },
  inputRow: { gap: 8 },
  textArea: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, minHeight: 80, textAlignVertical: 'top' },
  sliderRow: { flexDirection: 'row', gap: 4, justifyContent: 'space-between' },
  sliderDot: { width: 30, height: 30, borderRadius: 15, backgroundColor: '#F3F4F6', justifyContent: 'center', alignItems: 'center' },
  sliderNum: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#0EA5E9', borderRadius: 14, paddingVertical: 16, marginTop: 24 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  bold: { fontWeight: '800' },
  italic: { fontStyle: 'italic' },

  // Guidance
  guidanceCard: { backgroundColor: '#F0F9FF', borderRadius: 16, padding: 18, marginBottom: 20, borderWidth: 1, borderColor: '#BAE6FD' },
  guidanceText: { fontSize: 15, color: '#0C4A6E', lineHeight: 24 },

  // DON'Ts
  dontsTitle: { fontSize: 18, fontWeight: '800', color: '#0C4A6E', marginBottom: 4 },
  dontsSubtitle: { fontSize: 13, color: '#0284C7', marginBottom: 14 },
  dontCard: { flexDirection: 'row', gap: 10, backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#E0F2FE', alignItems: 'flex-start' },
  dontNumBg: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#0EA5E9', justifyContent: 'center', alignItems: 'center' },
  dontNumText: { fontSize: 13, fontWeight: '800', color: '#FFF' },
  dontTitle: { fontSize: 13, fontWeight: '800', color: '#0C4A6E' },
  dontDetail: { fontSize: 12, color: '#075985', marginTop: 2, lineHeight: 17 },

  // Question
  questionBox: { flexDirection: 'row', gap: 10, backgroundColor: '#F0F9FF', borderRadius: 14, padding: 16, marginTop: 16, marginBottom: 20, borderWidth: 1, borderColor: '#BAE6FD' },
  questionText: { fontSize: 14, color: '#0C4A6E', flex: 1, lineHeight: 22 },

  // Choice
  choiceTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 12 },
  choiceRow: { gap: 10 },
  choiceBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, borderRadius: 14, paddingVertical: 16 },
  choiceBtnYes: { backgroundColor: '#0EA5E9' },
  choiceBtnNo: { backgroundColor: '#94A3B8' },
  choiceBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },

  // Timer
  timerLabel: { fontSize: 16, fontWeight: '600', color: 'rgba(255,255,255,0.7)', marginBottom: 24, fontStyle: 'italic' },
  timerCircle: { width: 220, height: 220, borderRadius: 110, borderWidth: 3, borderColor: 'rgba(255,255,255,0.3)', justifyContent: 'center', alignItems: 'center' },
  timerInnerCircle: { width: 200, height: 200, borderRadius: 100, justifyContent: 'center', alignItems: 'center' },
  timerText: { fontSize: 52, fontWeight: '800', color: '#FFF' },
  timerSubtext: { fontSize: 13, color: 'rgba(255,255,255,0.7)', marginTop: -2 },
  timerMessage: { fontSize: 28, fontWeight: '800', color: '#FFF', marginTop: 32 },
  timerSubMessage: { fontSize: 14, color: 'rgba(255,255,255,0.7)', textAlign: 'center', lineHeight: 20, marginTop: 8 },
  breatheGuide: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 12, paddingHorizontal: 16, paddingVertical: 10, marginTop: 24 },
  breatheText: { fontSize: 13, color: 'rgba(255,255,255,0.8)' },
  abandonBtn: { marginTop: 32, paddingVertical: 14, paddingHorizontal: 20, alignItems: 'center' },
  abandonText: {
    fontSize: 17,
    color: 'rgba(255,255,255,0.92)',
    fontWeight: '700',
    textDecorationLine: 'underline',
    textDecorationColor: 'rgba(255,255,255,0.92)',
    letterSpacing: 0.2,
  },

  // Completion
  completionCard: { borderRadius: 20, padding: 24, alignItems: 'center', marginBottom: 16 },
  congratsEmoji: { marginBottom: 12 },
  congratsTitle: { fontSize: 24, fontWeight: '800', color: '#065F46', marginBottom: 10 },
  congratsText: { fontSize: 15, color: '#047857', textAlign: 'center', lineHeight: 23 },
  congratsSub: { fontSize: 13, color: '#059669', textAlign: 'center', marginTop: 10, fontStyle: 'italic' },
  contactBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(255,255,255,0.6)', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8, marginTop: 12 },
  contactText: { fontSize: 13, fontWeight: '600', color: '#D97706' },
  shiftBadge: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#ECFDF5', borderRadius: 10, paddingVertical: 8, marginTop: 8 },
  shiftText: { fontSize: 13, fontWeight: '600', color: '#059669' },

  // EQ Summary
  eqCard: { borderRadius: 20, padding: 24, width: '100%', alignItems: 'center', marginBottom: 20 },
  eqTitleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: 16 },
  eqTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  eqRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', width: '100%' },
  // ─── EQ breakdown info modal ───
  eqInfoOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  eqInfoCard: { width: '100%', maxWidth: 460, backgroundColor: '#FFFFFF', borderRadius: 18, padding: 22, gap: 14 },
  eqInfoHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  eqInfoTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A' },
  eqInfoIntro: { fontSize: 13, color: '#475569', lineHeight: 19 },
  eqInfoTotalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#E2E8F0', paddingTop: 10, marginTop: 6 },
  eqInfoTotalLabel: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  eqInfoTotalValue: { fontSize: 18, fontWeight: '800', color: '#0EA5E9' },
  eqInfoFooter: { fontSize: 11, color: '#64748B', lineHeight: 16, fontStyle: 'italic', marginTop: 4 },
  eqItem: { alignItems: 'center' },
  eqNum: { fontSize: 26, fontWeight: '800', color: '#FFF' },
  eqLabel: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  eqDivider: { width: 1, height: 30, backgroundColor: 'rgba(255,255,255,0.3)' },
  doneBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 8 },
  doneBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#FFFFFF',
    borderColor: '#0EA5E9',
    borderWidth: 1.5,
    borderRadius: 14,
    paddingVertical: 14,
    marginTop: 10,
  },
  secondaryBtnText: { fontSize: 15, fontWeight: '700', color: '#0EA5E9' },
});
