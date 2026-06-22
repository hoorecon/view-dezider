/**
 * /p/[slug]  — Branded public org sub-portal (in-app version of the HTML widget)
 *
 * Tabs:
 *   • About    — org branding, primary_color, mission, links
 *   • Surveys  — list active org surveys, submit responses (anon allowed)
 *   • Reviews  — public reviews (delegates to /api/p/{slug}/reviews)
 *   • Feedback — submit complaint/suggestion/idea
 *
 * Public read endpoints — no auth required for browsing (auth is honoured if
 * the user is logged in so submissions are linked to their account).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, KeyboardAvoidingView, Platform, Modal, Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

type Tab = 'about' | 'surveys' | 'reviews' | 'feedback';

interface OrgBrand {
  slug: string;
  org_id: string;
  display_name: string;
  about?: string;
  website?: string;
  email?: string;
  state?: string;
  district?: string;
  categories?: string[];
  primary_color: string;
  logo_uri?: string;
  active_member_count?: number;
  total_feedback_handled?: number;
}

interface SurveyQuestion {
  qid: string;
  text: string;
  qtype: 'short_text' | 'long_text' | 'single_select' | 'multi_select' | 'rating_5' | 'yes_no' | 'number';
  options?: string[];
  required?: boolean;
  helper?: string;
}

interface Survey {
  survey_id: string;
  title: string;
  description?: string;
  questions: SurveyQuestion[];
  is_active: boolean;
  accepts_anon: boolean;
  response_count?: number;
}

export default function PublicOrgPortal() {
  const router = useRouter();
  const { slug: rawSlug } = useLocalSearchParams();
  const slug = String(rawSlug || '').trim();

  const [tab, setTab] = useState<Tab>('about');
  const [org, setOrg] = useState<OrgBrand | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrg = useCallback(async () => {
    if (!slug) return;
    try {
      setLoading(true);
      const r = await api.get(`/p/${slug}`);
      setOrg(r.data?.org || null);
      setError(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Org not found');
    } finally { setLoading(false); }
  }, [slug]);

  useEffect(() => { loadOrg(); }, [loadOrg]);

  const primary = org?.primary_color || '#7C3AED';

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  if (error || !org) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.headerBar}>
          <TouchableOpacity onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
          <Text style={styles.headerTitle}>Org Portal</Text>
          <View style={{ width: 22 }} />
        </View>
        <View style={styles.center}>
          <Ionicons name="alert-circle" size={48} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textPrimary, marginTop: 8, fontSize: 14 }}>{error || 'Org not found'}</Text>
          <Text style={{ color: COLORS.textMuted, marginTop: 4, fontSize: 12 }}>slug: {slug}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header — themed */}
      <View style={[styles.headerBar, { backgroundColor: primary }]}>
        <TouchableOpacity onPress={() => safeBack(router)} style={{ padding: 4 }}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{org.display_name}</Text>
        <TouchableOpacity onPress={() => org.website && Linking.openURL(org.website.startsWith('http') ? org.website : `https://${org.website}`)} style={{ padding: 4, opacity: org.website ? 1 : 0 }}>
          <Ionicons name="open-outline" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>

      {/* Hero band */}
      <View style={[styles.hero, { backgroundColor: primary + '15', borderColor: primary + '40' }]}>
        <View style={[styles.logoCircle, { backgroundColor: primary }]}>
          <Text style={{ color: '#FFF', fontSize: 22, fontWeight: '700' }}>
            {(org.display_name || 'O')[0]}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[styles.orgName, { color: primary }]}>{org.display_name}</Text>
          {!!org.about && <Text style={styles.orgAbout} numberOfLines={3}>{org.about}</Text>}
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
            {!!org.state && <Text style={styles.tag}>{org.state}</Text>}
            {!!org.district && <Text style={styles.tag}>{org.district}</Text>}
            {(org.categories || []).slice(0, 3).map(c => <Text key={c} style={styles.tag}>{c}</Text>)}
          </View>
        </View>
      </View>

      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 12, gap: 6 }} style={styles.tabsRow}>
        {(['about', 'surveys', 'reviews', 'feedback'] as Tab[]).map(t => (
          <TouchableOpacity
            key={t}
            testID={`pp-tab-${t}`}
            onPress={() => setTab(t)}
            style={[styles.tab, tab === t && { borderBottomColor: primary, borderBottomWidth: 2 }]}
          >
            <Text style={[styles.tabText, tab === t && { color: primary, fontWeight: '700' }]}>
              {t === 'about' ? 'About' : t === 'surveys' ? 'Surveys' : t === 'reviews' ? 'Reviews' : 'Feedback'}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'about' && <AboutTab org={org} primary={primary} />}
      {tab === 'surveys' && <SurveysTab slug={slug} primary={primary} />}
      {tab === 'reviews' && <ReviewsTab slug={slug} primary={primary} />}
      {tab === 'feedback' && <FeedbackTab slug={slug} primary={primary} />}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// About
// ---------------------------------------------------------------------------
function AboutTab({ org, primary }: { org: OrgBrand; primary: string }) {
  return (
    <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }}>
      <View style={styles.card}>
        <Text style={[styles.sectionH, { color: primary }]}>About</Text>
        {!!org.about ? <Text style={styles.body}>{org.about}</Text> :
          <Text style={{ color: COLORS.textMuted, fontSize: 12 }}>No description provided.</Text>}
      </View>

      <View style={styles.card}>
        <Text style={[styles.sectionH, { color: primary }]}>Contact</Text>
        {!!org.email && (
          <TouchableOpacity onPress={() => Linking.openURL(`mailto:${org.email}`)} style={styles.contactRow}>
            <Ionicons name="mail" size={16} color={primary} />
            <Text style={[styles.body, { color: primary }]}>{org.email}</Text>
          </TouchableOpacity>
        )}
        {!!org.website && (
          <TouchableOpacity onPress={() => Linking.openURL(org.website!.startsWith('http') ? org.website! : `https://${org.website}`)} style={styles.contactRow}>
            <Ionicons name="globe" size={16} color={primary} />
            <Text style={[styles.body, { color: primary }]}>{org.website}</Text>
          </TouchableOpacity>
        )}
        {!org.email && !org.website && <Text style={{ color: COLORS.textMuted, fontSize: 12 }}>No contact info available.</Text>}
      </View>

      <View style={styles.card}>
        <Text style={[styles.sectionH, { color: primary }]}>Stats</Text>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <View style={[styles.statBox, { borderColor: primary + '40' }]}>
            <Text style={[styles.statNum, { color: primary }]}>{org.active_member_count ?? 0}</Text>
            <Text style={styles.statLabel}>Members</Text>
          </View>
          <View style={[styles.statBox, { borderColor: primary + '40' }]}>
            <Text style={[styles.statNum, { color: primary }]}>{org.total_feedback_handled ?? 0}</Text>
            <Text style={styles.statLabel}>Feedback handled</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Surveys
// ---------------------------------------------------------------------------
function SurveysTab({ slug, primary }: { slug: string; primary: string }) {
  const [items, setItems] = useState<Survey[]>([]);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState<Survey | null>(null);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get(`/p/${slug}/surveys`);
      setItems(r.data?.items || []);
    } catch (e: any) { showAlert('Surveys', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [slug]);

  useEffect(() => { load(); }, [load]);

  return (
    <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }}>
      {loading ? <ActivityIndicator color={primary} /> : items.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="document-text-outline" size={36} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No active surveys</Text>
        </View>
      ) : items.map(s => (
        <View key={s.survey_id} style={[styles.card, { borderLeftWidth: 4, borderLeftColor: primary }]}>
          <Text style={styles.cardTitle}>{s.title}</Text>
          {!!s.description && <Text style={styles.body} numberOfLines={3}>{s.description}</Text>}
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
            <Text style={styles.tag}>{s.questions?.length || 0} questions</Text>
            <Text style={styles.tag}>{s.response_count || 0} responses</Text>
            {s.accepts_anon && <Text style={[styles.tag, { backgroundColor: primary + '22', color: primary }]}>Anon OK</Text>}
          </View>
          <TouchableOpacity
            testID={`pp-survey-take-${s.survey_id}`}
            style={[styles.btnPrimary, { backgroundColor: primary, marginTop: 10 }]}
            onPress={() => setPicked(s)}
          >
            <Ionicons name="create" size={14} color="#FFF" />
            <Text style={styles.btnPrimaryText}>Take survey</Text>
          </TouchableOpacity>
        </View>
      ))}

      {picked && <SurveyResponseSheet slug={slug} survey={picked} primary={primary} onClose={() => { setPicked(null); load(); }} />}
    </ScrollView>
  );
}

function SurveyResponseSheet({ slug, survey, primary, onClose }: { slug: string; survey: Survey; primary: string; onClose: () => void }) {
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const missing = (survey.questions || []).filter(q => {
      if (!q.required) return false;
      const v = answers[q.qid];
      return v === undefined || v === '' || (Array.isArray(v) && v.length === 0);
    });
    if (missing.length) {
      return showAlert('Required', `Please answer: ${missing.map(m => m.text).join(', ')}`);
    }
    try { setSubmitting(true);
      await api.post(`/p/${slug}/surveys/${survey.survey_id}/submit`, {
        answers,
        contact_name: contactName || undefined,
        contact_email: contactEmail || undefined,
      });
      showAlert('Thanks!', 'Your response has been recorded.');
      onClose();
    } catch (e: any) { showAlert('Submit failed', e?.response?.data?.detail || e.message); }
    finally { setSubmitting(false); }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text style={[styles.sheetTitle, { color: primary, flex: 1 }]} numberOfLines={2}>{survey.title}</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
          </View>

          <ScrollView style={{ maxHeight: 460 }}>
            {!!survey.description && <Text style={[styles.body, { marginBottom: 8 }]}>{survey.description}</Text>}

            {survey.questions.map(q => (
              <View key={q.qid} style={{ marginBottom: 14 }}>
                <Text style={styles.fieldLabel}>{q.text}{q.required ? ' *' : ''}</Text>
                {!!q.helper && <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>{q.helper}</Text>}

                {q.qtype === 'short_text' && (
                  <TextInput style={styles.input} value={answers[q.qid] || ''} onChangeText={v => setAnswers({ ...answers, [q.qid]: v })} placeholderTextColor={COLORS.textMuted} />
                )}
                {q.qtype === 'long_text' && (
                  <TextInput style={[styles.input, { minHeight: 80 }]} multiline value={answers[q.qid] || ''} onChangeText={v => setAnswers({ ...answers, [q.qid]: v })} placeholderTextColor={COLORS.textMuted} />
                )}
                {q.qtype === 'number' && (
                  <TextInput style={styles.input} keyboardType="numeric" value={String(answers[q.qid] ?? '')} onChangeText={v => setAnswers({ ...answers, [q.qid]: v })} placeholderTextColor={COLORS.textMuted} />
                )}
                {q.qtype === 'rating_5' && (
                  <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
                    {[1, 2, 3, 4, 5].map(n => (
                      <TouchableOpacity key={n} testID={`q-${q.qid}-${n}`} onPress={() => setAnswers({ ...answers, [q.qid]: n })}>
                        <Ionicons name={(answers[q.qid] || 0) >= n ? 'star' : 'star-outline'} size={28} color={primary} />
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                {q.qtype === 'yes_no' && (
                  <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
                    {['yes', 'no'].map(v => (
                      <TouchableOpacity key={v} onPress={() => setAnswers({ ...answers, [q.qid]: v })} style={[styles.choiceChip, answers[q.qid] === v && { backgroundColor: primary + '22', borderColor: primary }]}>
                        <Text style={[styles.choiceText, answers[q.qid] === v && { color: primary, fontWeight: '700' }]}>{v.toUpperCase()}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                {q.qtype === 'single_select' && (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                    {(q.options || []).map(opt => (
                      <TouchableOpacity key={opt} onPress={() => setAnswers({ ...answers, [q.qid]: opt })} style={[styles.choiceChip, answers[q.qid] === opt && { backgroundColor: primary + '22', borderColor: primary }]}>
                        <Text style={[styles.choiceText, answers[q.qid] === opt && { color: primary, fontWeight: '700' }]}>{opt}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                {q.qtype === 'multi_select' && (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                    {(q.options || []).map(opt => {
                      const selected = (answers[q.qid] || []).includes(opt);
                      return (
                        <TouchableOpacity key={opt} onPress={() => {
                          const current = answers[q.qid] || [];
                          const next = selected ? current.filter((x: string) => x !== opt) : [...current, opt];
                          setAnswers({ ...answers, [q.qid]: next });
                        }} style={[styles.choiceChip, selected && { backgroundColor: primary + '22', borderColor: primary }]}>
                          <Text style={[styles.choiceText, selected && { color: primary, fontWeight: '700' }]}>
                            {selected ? '✓ ' : ''}{opt}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
              </View>
            ))}

            {survey.accepts_anon && (
              <View style={{ marginTop: 8, padding: 10, backgroundColor: '#F9FAFB', borderRadius: 8 }}>
                <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 6 }}>Optional contact info (only if you'd like a follow-up)</Text>
                <TextInput style={styles.input} placeholder="Your name" placeholderTextColor={COLORS.textMuted} value={contactName} onChangeText={setContactName} />
                <TextInput style={[styles.input, { marginTop: 6 }]} placeholder="Your email" placeholderTextColor={COLORS.textMuted} keyboardType="email-address" autoCapitalize="none" value={contactEmail} onChangeText={setContactEmail} />
              </View>
            )}
          </ScrollView>

          <TouchableOpacity testID="pp-survey-submit" onPress={submit} disabled={submitting} style={[styles.btnPrimary, { backgroundColor: primary, marginTop: 14 }]}>
            {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Submit response</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Reviews
// ---------------------------------------------------------------------------
function ReviewsTab({ slug, primary }: { slug: string; primary: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { (async () => {
    try { const r = await api.get(`/p/${slug}/reviews`); setData(r.data); }
    catch (e: any) { showAlert('Reviews', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  })(); }, [slug]);
  if (loading) return <View style={{ padding: 32 }}><ActivityIndicator color={primary} /></View>;
  const summary = data?.summary || {};
  const items = data?.items || [];
  return (
    <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }}>
      <View style={[styles.card, { borderLeftWidth: 4, borderLeftColor: primary }]}>
        <Text style={[styles.sectionH, { color: primary }]}>Aggregate</Text>
        <View style={{ flexDirection: 'row', gap: 14 }}>
          <View><Text style={[styles.statNum, { color: primary }]}>{summary.overall_avg ?? 0}</Text><Text style={styles.statLabel}>★ Avg</Text></View>
          <View><Text style={[styles.statNum, { color: primary }]}>{summary.total_reviews ?? 0}</Text><Text style={styles.statLabel}>Reviews</Text></View>
        </View>
      </View>
      {items.length === 0 ? <View style={styles.empty}><Text style={{ color: COLORS.textMuted }}>No reviews yet</Text></View> :
        items.map((r: any, i: number) => (
          <View key={r.review_id || `r${i}`} style={styles.card}>
            <Text style={styles.cardTitle}>{r.solution_name}</Text>
            <Text style={styles.body} numberOfLines={4}>{r.review_text || r.short_review || ''}</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
              <Text style={[styles.tag, { backgroundColor: primary + '22', color: primary }]}>★ {r.overall_rating}</Text>
              {r.reviewer_segment && <Text style={styles.tag}>{r.reviewer_segment}</Text>}
            </View>
          </View>
        ))}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------
function FeedbackTab({ slug, primary }: { slug: string; primary: string }) {
  const [type, setType] = useState<'complaint' | 'suggestion' | 'idea'>('suggestion');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim() || !description.trim()) {
      return showAlert('Required', 'Title and description are required');
    }
    try { setBusy(true);
      await api.post(`/p/${slug}/feedback`, {
        feedback_type: type, title, description,
        contact_name: contactName || undefined,
        contact_email: contactEmail || undefined,
      });
      showAlert('Thanks!', 'Your feedback has been submitted.');
      setTitle(''); setDescription(''); setContactName(''); setContactEmail('');
    } catch (e: any) { showAlert('Submit failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }}>
        <View style={styles.card}>
          <Text style={[styles.sectionH, { color: primary }]}>Submit feedback</Text>

          <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
            {(['complaint', 'suggestion', 'idea'] as const).map(t => (
              <TouchableOpacity key={t} onPress={() => setType(t)} style={[styles.choiceChip, type === t && { backgroundColor: primary + '22', borderColor: primary }]}>
                <Text style={[styles.choiceText, type === t && { color: primary, fontWeight: '700' }]}>{t.charAt(0).toUpperCase() + t.slice(1)}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.fieldLabel}>Title *</Text>
          <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder="Short title" placeholderTextColor={COLORS.textMuted} />

          <Text style={styles.fieldLabel}>Description *</Text>
          <TextInput style={[styles.input, { minHeight: 100 }]} multiline value={description} onChangeText={setDescription} placeholder="Tell us more" placeholderTextColor={COLORS.textMuted} />

          <Text style={styles.fieldLabel}>Your name (optional)</Text>
          <TextInput style={styles.input} value={contactName} onChangeText={setContactName} placeholderTextColor={COLORS.textMuted} />

          <Text style={styles.fieldLabel}>Your email (optional)</Text>
          <TextInput style={styles.input} value={contactEmail} onChangeText={setContactEmail} keyboardType="email-address" autoCapitalize="none" placeholderTextColor={COLORS.textMuted} />

          <TouchableOpacity testID="pp-feedback-submit" onPress={submit} disabled={busy} style={[styles.btnPrimary, { backgroundColor: primary, marginTop: 14 }]}>
            {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Submit feedback</Text>}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ---------------------------------------------------------------------------
// styles
// ---------------------------------------------------------------------------
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  headerBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: COLORS.primary },
  headerTitle: { color: '#FFF', fontSize: 16, fontWeight: '700', flex: 1, marginHorizontal: 10 },

  hero: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderBottomWidth: 1 },
  logoCircle: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  orgName: { fontSize: 17, fontWeight: '700' },
  orgAbout: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },
  tag: { fontSize: 11, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, backgroundColor: '#F3F4F6', color: COLORS.textSecondary, fontWeight: '600' },

  tabsRow: { backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider, maxHeight: 46 },
  tab: { paddingHorizontal: 14, paddingVertical: 12 },
  tabText: { fontSize: 13, color: COLORS.textSecondary, fontWeight: '500' },

  card: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  sectionH: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  body: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  empty: { alignItems: 'center', padding: 40 },

  statBox: { flex: 1, padding: 12, borderRadius: 8, borderWidth: 1, alignItems: 'center', backgroundColor: '#FAFAFA' },
  statNum: { fontSize: 24, fontWeight: '800' },
  statLabel: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },

  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },

  choiceChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  choiceText: { fontSize: 12, color: COLORS.textSecondary },

  btnPrimary: { paddingVertical: 12, paddingHorizontal: 14, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  btnPrimaryText: { color: '#FFF', fontSize: 14, fontWeight: '700' },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '92%' },
  sheetTitle: { fontSize: 16, fontWeight: '700' },
});
