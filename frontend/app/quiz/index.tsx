/**
 * Guest Decision-Style Quiz — the "marketing HOOK" entry point.
 *
 * URL: /quiz  (also intended to be served from quiz.jelcos.ai subdomain).
 *
 * Behaviour:
 *  1. Public — no login required to *take* the quiz.
 *  2. Collects answers + optional name / email / WhatsApp / gender.
 *  3. POSTs to /api/quiz/guest-submit → server returns a short-lived
 *     `quiz_token` (result is NOT revealed here).
 *  4. Stashes the token in AsyncStorage as `pending_quiz_token` and sends
 *     the visitor to /auth/login (via Google or Email sign-in).
 *  5. After a successful sign-in, `getPostAuthRoute()` redirects to
 *     /quiz/result?token=… which claims the token and renders the result
 *     with all sharing options (PDF, WhatsApp, Email) available.
 */
import React, { useEffect, useState, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { COLORS } from '../../src/constants/colors';
import { useAuthStore } from '../../src/store/authStore';

const API = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api';

interface Q { id: string; text: string; mode: string }

export default function GuestQuizScreen() {
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const { isAuthenticated } = useAuthStore();

  const [questions, setQuestions] = useState<Q[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [gender, setGender] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  useEffect(() => {
    axios.get(`${API}/quiz/questions`)
      .then(r => setQuestions(r.data?.questions || []))
      .catch(() => setErr('Could not load quiz questions. Please refresh.'))
      .finally(() => setLoading(false));
  }, []);

  const setAns = (qid: string, v: number) => setAnswers((a) => ({ ...a, [qid]: v }));

  const submit = async () => {
    const unanswered = questions.filter((q) => !answers[q.id]);
    if (unanswered.length > 0) {
      setErr(`Please answer all ${questions.length} questions to see your result.`);
      return;
    }
    setErr('');
    setBusy(true);
    try {
      const r = await axios.post(`${API}/quiz/guest-submit`, {
        answers, name: name.trim(), email: email.trim(), whatsapp: whatsapp.trim(), gender,
      });
      const token = r.data?.quiz_token;
      if (!token) throw new Error('No token');
      await AsyncStorage.setItem('pending_quiz_token', token);
      if (isAuthenticated) {
        router.replace(`/quiz/result?token=${token}` as any);
      } else {
        router.replace('/auth/login' as any);
      }
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <ActivityIndicator color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView ref={scrollRef} contentContainerStyle={s.wrap}>
        <View style={s.hero}>
          <View style={s.badge}><Ionicons name="sparkles" size={14} color="#fff" /><Text style={s.badgeT}>Free · No signup to start</Text></View>
          <Text style={s.title}>Discover Your Decision-Making Style</Text>
          <Text style={s.sub}>16 quick questions · 2 minutes · Get a personalized breakdown across Emotional, Logical, Intuitive & Consciousness modes.</Text>
        </View>

        <View style={s.lead}>
          <Text style={s.leadLabel}>Where should we send your result? (optional)</Text>
          <TextInput style={s.leadInput} value={name} onChangeText={setName} placeholder="Your name" placeholderTextColor="#94A3B8" />
          <TextInput style={s.leadInput} value={email} onChangeText={setEmail} placeholder="Email" placeholderTextColor="#94A3B8" keyboardType="email-address" autoCapitalize="none" />
          <TextInput style={s.leadInput} value={whatsapp} onChangeText={setWhatsapp} placeholder="WhatsApp (e.g. +9198…)" placeholderTextColor="#94A3B8" keyboardType="phone-pad" />
          <View style={s.gRow}>
            {['Male', 'Female', 'Other', ''].map((g) => {
              const on = gender === g; const label = g || 'Prefer not to say';
              return (
                <TouchableOpacity key={label} onPress={() => setGender(g)} style={[s.gChip, on && s.gChipOn]}>
                  <Text style={[s.gChipT, on && s.gChipTOn]}>{label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <Text style={s.instr}>Rate each statement from 1 (Strongly Disagree) to 5 (Strongly Agree)</Text>

        {questions.map((q, idx) => (
          <View key={q.id} style={s.qCard}>
            <Text style={s.qNum}>Question {idx + 1} of {questions.length}</Text>
            <Text style={s.qText}>{q.text}</Text>
            <View style={s.rRow}>
              {[1, 2, 3, 4, 5].map((v) => (
                <View key={v} style={s.rCell}>
                  <TouchableOpacity
                    style={[s.rBtn, answers[q.id] === v && s.rBtnOn]}
                    onPress={() => setAns(q.id, v)}
                  >
                    <Text style={[s.rBtnT, answers[q.id] === v && s.rBtnTOn]}>{v}</Text>
                  </TouchableOpacity>
                  <Text style={s.rLbl} numberOfLines={2}>
                    {v === 1 ? 'Strongly Disagree' : v === 2 ? 'Disagree' : v === 3 ? 'Neutral' : v === 4 ? 'Agree' : 'Strongly Agree'}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        ))}

        {!!err && <Text style={s.err}>{err}</Text>}

        <TouchableOpacity style={[s.cta, busy && { opacity: 0.6 }]} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : (
            <>
              <Ionicons name="lock-closed" size={16} color="#fff" />
              <Text style={s.ctaT}>See My Decision Style</Text>
            </>
          )}
        </TouchableOpacity>
        <Text style={s.footNote}>
          {isAuthenticated
            ? "You'll see your result on the next screen — download PDF & share via WhatsApp / Email."
            : "Sign in with Google or Email to unlock your personalized result, PDF and sharing."}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  wrap: { padding: 16, paddingBottom: 48, maxWidth: 780, width: '100%', alignSelf: 'center' },
  hero: { alignItems: 'center', marginBottom: 16 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#7C3AED', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20 },
  badgeT: { color: '#fff', fontSize: 11, fontWeight: '700' },
  title: { fontSize: Platform.OS === 'web' ? 28 : 22, fontWeight: '800', color: COLORS.textPrimary, textAlign: 'center', marginTop: 10 },
  sub: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, lineHeight: 19 },
  lead: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border, gap: 8 },
  leadLabel: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '700' },
  leadInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  gRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  gChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F8FAFC' },
  gChipOn: { backgroundColor: '#EEF2FF', borderColor: COLORS.primary },
  gChipT: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  gChipTOn: { color: COLORS.primary },
  instr: { fontSize: 12, color: COLORS.textSecondary, textAlign: 'center', marginTop: 4, marginBottom: 8 },
  qCard: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  qNum: { fontSize: 11, color: '#7C3AED', fontWeight: '800', marginBottom: 6 },
  qText: { fontSize: 15, color: COLORS.textPrimary, lineHeight: 22, marginBottom: 12 },
  rRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  rCell: { flex: 1, alignItems: 'center', paddingHorizontal: 2 },
  rBtn: { width: 42, height: 42, borderRadius: 21, backgroundColor: COLORS.background, borderWidth: 2, borderColor: COLORS.border, alignItems: 'center', justifyContent: 'center' },
  rBtnOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  rBtnT: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  rBtnTOn: { color: COLORS.white },
  rLbl: { fontSize: 10, color: COLORS.textMuted, textAlign: 'center', marginTop: 6, lineHeight: 12, minHeight: 24 },
  err: { color: '#DC2626', fontSize: 12, textAlign: 'center', marginTop: 8 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', paddingVertical: 14, borderRadius: 14, marginTop: 14 },
  ctaT: { color: '#fff', fontSize: 15, fontWeight: '800' },
  footNote: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 10, lineHeight: 16 },
});
