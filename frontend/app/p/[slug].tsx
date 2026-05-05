/**
 * Public Org Sub-Portal — `/p/[slug]`
 *
 * No-auth-required public page that surfaces an Org's branded sub-portal:
 * about, recent resolved feedback, and a feedback submission form.
 *
 * Designed to be reachable directly via expo-router, AND embeddable as an
 * iframe (via /api/embed/{slug}) when the Org / Govt dept hosts the widget
 * on their own domain.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TextInput, TouchableOpacity,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

interface OrgPortal {
  slug: string;
  org_id: string;
  display_name: string;
  about?: string;
  website?: string;
  email?: string;
  state?: string;
  district?: string;
  categories?: string[];
  primary_color?: string;
  logo_uri?: string;
  active_member_count?: number;
  total_feedback_handled?: number;
}

interface PortalConfig {
  show_feedback_form: boolean;
  show_resolved_list: boolean;
  primary_cta_label: string;
}

interface FeedbackItem {
  feedback_id: string;
  feedback_type: string;
  title: string;
  description_short: string;
  status: string;
  created_at?: string;
  resolved_at?: string;
  response_text?: string;
}

const FEEDBACK_TYPES = [
  { id: 'complaint', label: 'Complaint', icon: 'alert-circle' },
  { id: 'suggestion', label: 'Suggestion', icon: 'bulb' },
  { id: 'idea', label: 'Idea', icon: 'sparkles' },
];

export default function PublicOrgPortal() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const slug = String(params.slug || '');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [org, setOrg] = useState<OrgPortal | null>(null);
  const [config, setConfig] = useState<PortalConfig | null>(null);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [reviews, setReviews] = useState<any | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<string | null>(null);

  // Form state
  const [type, setType] = useState('suggestion');
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [district, setDistrict] = useState('');

  useEffect(() => {
    if (slug) loadPortal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const loadPortal = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/p/${slug}`, { skipAuth: true } as any);
      setOrg(res.data?.org || null);
      setConfig(res.data?.config || null);
      // Resolved feedback
      try {
        const fb = await api.get(`/p/${slug}/feedback/public`, { skipAuth: true } as any);
        setFeedback(fb.data?.items || []);
      } catch { /* swallow — feedback list is optional */ }
      // ReviewNet showcase
      try {
        const rv = await api.get(`/p/${slug}/reviews?limit=12`, { skipAuth: true } as any);
        setReviews(rv.data || null);
      } catch { /* swallow — reviews are optional */ }
    } catch (e: any) {
      setError(e?.response?.status === 404 ? 'This sub-portal does not exist or is not yet published.' : 'Could not load this page.');
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    setSubmitted(null);
    if (!title.trim() || !desc.trim()) {
      setError('Please fill in title and description.');
      return;
    }
    setSubmitting(true);
    try {
      const body: any = {
        feedback_type: type,
        title: title.trim(),
        description: desc.trim(),
      };
      if (contactName.trim()) body.contact_name = contactName.trim();
      if (contactEmail.trim()) body.contact_email = contactEmail.trim();
      if (district.trim()) body.location_district = district.trim();
      const res = await api.post(`/p/${slug}/feedback`, body, { skipAuth: true } as any);
      setSubmitted(res.data?.feedback_id || 'received');
      setTitle(''); setDesc(''); setContactName(''); setContactEmail(''); setDistrict('');
    } catch {
      setError('Could not submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  if (error && !org) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errCard}>
          <Ionicons name="alert-circle" size={32} color="#EF4444" />
          <Text style={styles.errTitle}>Cannot load portal</Text>
          <Text style={styles.errBody}>{error}</Text>
          <TouchableOpacity onPress={() => router.replace('/' as any)} style={styles.errBtn}>
            <Text style={styles.errBtnText}>Go home</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  if (!org) return null;

  const color = org.primary_color || '#7C3AED';
  const ctaLabel = config?.primary_cta_label || 'Send your feedback';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
          {/* Branded header */}
          <View style={[styles.header, { backgroundColor: color }]}>
            <Text style={styles.headerTitle}>{org.display_name}</Text>
            <Text style={styles.headerSub}>
              {[org.state, org.district].filter(Boolean).join(' · ')}
              {(org.total_feedback_handled || 0) > 0 ? `  ·  ${org.total_feedback_handled} handled` : ''}
            </Text>
          </View>

          <View style={{ padding: 16 }}>
            {/* About */}
            {org.about ? (
              <View style={styles.card}>
                <View style={styles.tagRow}>
                  {(org.categories || []).map(c => (
                    <View key={c} style={[styles.tag, { backgroundColor: color + '15' }]}>
                      <Text style={[styles.tagText, { color }]}>{c}</Text>
                    </View>
                  ))}
                </View>
                <Text style={styles.aboutText}>{org.about}</Text>
                {!!org.website && (
                  <Text style={[styles.aboutText, { color, marginTop: 6 }]}>{org.website}</Text>
                )}
              </View>
            ) : null}

            {/* Feedback form */}
            {config?.show_feedback_form && (
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>{ctaLabel}</Text>
                <View style={styles.typeRow}>
                  {FEEDBACK_TYPES.map(t => {
                    const sel = type === t.id;
                    return (
                      <TouchableOpacity
                        key={t.id}
                        style={[styles.typeChip, sel && { backgroundColor: color, borderColor: color }]}
                        onPress={() => setType(t.id)}
                      >
                        <Ionicons name={t.icon as any} size={14} color={sel ? '#FFF' : color} />
                        <Text style={[styles.typeChipText, sel && { color: '#FFF' }]}>{t.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
                <TextInput style={styles.input} placeholder="Title (e.g. Pothole at Main St)"
                  placeholderTextColor={COLORS.textMuted} value={title} onChangeText={setTitle} maxLength={200} />
                <TextInput style={[styles.input, styles.textArea]} placeholder="Describe the issue or your idea..."
                  placeholderTextColor={COLORS.textMuted} value={desc} onChangeText={setDesc}
                  multiline numberOfLines={4} maxLength={4000} />
                <TextInput style={styles.input} placeholder="Your name (optional)" placeholderTextColor={COLORS.textMuted}
                  value={contactName} onChangeText={setContactName} maxLength={120} />
                <TextInput style={styles.input} placeholder="Your email (optional)" placeholderTextColor={COLORS.textMuted}
                  value={contactEmail} onChangeText={setContactEmail} maxLength={200} keyboardType="email-address" />
                <TextInput style={styles.input} placeholder="District (optional)" placeholderTextColor={COLORS.textMuted}
                  value={district} onChangeText={setDistrict} maxLength={120} />

                <TouchableOpacity
                  style={[styles.submitBtn, { backgroundColor: color }, submitting && { opacity: 0.6 }]}
                  onPress={submit} disabled={submitting}
                >
                  {submitting ? <ActivityIndicator size="small" color="#FFF" /> : (
                    <>
                      <Ionicons name="send" size={16} color="#FFF" />
                      <Text style={styles.submitText}>Submit</Text>
                    </>
                  )}
                </TouchableOpacity>

                {submitted && (
                  <View style={styles.successBox}>
                    <Ionicons name="checkmark-circle" size={18} color="#10B981" />
                    <Text style={styles.successText}>
                      Thanks — received (#{submitted.slice(0, 8)})
                    </Text>
                  </View>
                )}
                {!!error && (
                  <Text style={styles.errInline}>{error}</Text>
                )}
              </View>
            )}

            {/* Customer reviews — ReviewNet showcase */}
            {reviews && reviews.summary?.total_reviews > 0 && (
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Customer Reviews</Text>
                <Text style={{ fontSize: 13, color: COLORS.textSecondary, marginBottom: 10 }}>
                  {reviews.summary.total_reviews} review{reviews.summary.total_reviews === 1 ? '' : 's'} · avg {reviews.summary.overall_avg}/5 across all our solutions
                </Text>

                {/* Per-segment chips */}
                {Object.keys(reviews.summary.by_segment || {}).length > 0 && (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    {Object.entries(reviews.summary.by_segment as Record<string, any>).map(([seg, agg]: any) => (
                      <View key={seg} style={{ paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, backgroundColor: color + '22', borderWidth: 1, borderColor: color }}>
                        <Text style={{ fontSize: 11, fontWeight: '700', color }}>
                          {seg} · ★ {agg.avg}/5 ({agg.count})
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Top factors */}
                {reviews.summary.per_factor?.length > 0 && (
                  <View style={{ marginBottom: 12 }}>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: COLORS.textSecondary, marginBottom: 6 }}>Top factors</Text>
                    {reviews.summary.per_factor.slice(0, 5).map((f: any) => (
                      <View key={f.factor_id} style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                        <Text style={{ flex: 1, fontSize: 12, color: COLORS.textPrimary }} numberOfLines={1}>{f.factor_name}</Text>
                        <View style={{ width: 80, height: 6, backgroundColor: '#F1F5F9', borderRadius: 3, overflow: 'hidden', marginHorizontal: 8 }}>
                          <View style={{ width: `${(f.avg / 5) * 100}%`, height: 6, backgroundColor: color }} />
                        </View>
                        <Text style={{ fontSize: 11, color: COLORS.textPrimary, fontWeight: '600', width: 36, textAlign: 'right' }}>{f.avg}/5</Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Latest reviews */}
                {reviews.items?.slice(0, 5).map((rv: any) => (
                  <View key={rv.review_id} style={[styles.fbItem, { borderLeftColor: color }]}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 2 }}>
                      <Text style={styles.fbTitle}>{rv.title || rv.solution_name}</Text>
                      <Text style={{ fontSize: 12, fontWeight: '700', color }}>★ {rv.overall_rating}/5</Text>
                    </View>
                    <Text style={styles.fbMeta}>
                      {rv.reviewer_name} · {rv.reviewer_segment}{rv.reviewer_subsegment ? ` (${rv.reviewer_subsegment})` : ''}{rv.is_verified_buyer ? ' · ✓ verified' : ''}
                    </Text>
                    {!!rv.comment && <Text style={styles.fbDesc} numberOfLines={3}>{rv.comment}</Text>}
                  </View>
                ))}
              </View>
            )}

            {/* Recent resolved feedback */}
            {config?.show_resolved_list && feedback.length > 0 && (
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Recently handled</Text>
                {feedback.map(f => (
                  <View key={f.feedback_id} style={[styles.fbItem, { borderLeftColor: color }]}>
                    <Text style={styles.fbTitle}>{f.title}</Text>
                    <Text style={styles.fbMeta}>
                      {f.feedback_type?.toUpperCase()} · {f.status?.toUpperCase()}
                    </Text>
                    <Text style={styles.fbDesc}>{f.description_short}</Text>
                    {!!f.response_text && (
                      <Text style={[styles.fbDesc, { color: COLORS.textMuted, marginTop: 4 }]}>
                        Response: {f.response_text}
                      </Text>
                    )}
                  </View>
                ))}
              </View>
            )}

            <Text style={styles.footer}>Powered by Public Pulse</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { padding: 18 },
  headerTitle: { fontSize: 22, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 4 },
  card: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  tag: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 12 },
  tagText: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  aboutText: { fontSize: 13, color: COLORS.textPrimary, lineHeight: 19 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  typeRow: { flexDirection: 'row', gap: 6, marginBottom: 10 },
  typeChip: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 8, paddingHorizontal: 8,
    borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFF',
  },
  typeChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textPrimary },
  input: {
    backgroundColor: '#FFF', borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB',
    paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, marginBottom: 8,
    color: COLORS.textPrimary,
  },
  textArea: { minHeight: 80, textAlignVertical: 'top' },
  submitBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 12, borderRadius: 10,
  },
  submitText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  successBox: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#ECFDF5', padding: 10, borderRadius: 8, marginTop: 10,
  },
  successText: { color: '#065F46', fontSize: 12, fontWeight: '600' },
  errInline: { marginTop: 8, fontSize: 12, color: '#EF4444' },
  fbItem: { borderLeftWidth: 3, paddingLeft: 10, marginBottom: 10 },
  fbTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  fbMeta: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  fbDesc: { fontSize: 12, color: COLORS.textPrimary, marginTop: 4, lineHeight: 16 },
  footer: { textAlign: 'center', fontSize: 11, color: COLORS.textMuted, marginTop: 12 },
  errCard: { padding: 24, alignItems: 'center', marginTop: 80 },
  errTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  errBody: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginTop: 6 },
  errBtn: { marginTop: 16, paddingVertical: 10, paddingHorizontal: 20, borderRadius: 10, backgroundColor: COLORS.primary },
  errBtnText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
});
