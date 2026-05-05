import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  StyleSheet, Alert, Modal, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444', warning: '#F59E0B', gold: '#F59E0B',
};

const TYPE_COLORS: Record<string, string> = {
  PRODUCT: '#3B82F6', SERVICE: '#10B981', EVENT: '#F59E0B',
  PROJECT: '#8B5CF6', PERSON_CONTACT: '#EC4899',
};
const TYPE_ICONS: Record<string, string> = {
  PRODUCT: 'cube', SERVICE: 'construct', EVENT: 'calendar',
  PROJECT: 'rocket', PERSON_CONTACT: 'person',
};

const DEFAULT_FACTORS = [
  'Trustworthiness', 'Quality', 'Reliability', 'Value for Money',
  'User Experience', 'Customer Support', 'Innovation', 'Accessibility',
];

export default function SolutionDetailScreen() {
  const router = useRouter();
  const { solution_id } = useLocalSearchParams();
  const { session } = useAuthStore();

  const [solution, setSolution] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'quantitative' | 'reviews'>('overview');

  // ReviewNet state (replaces legacy `solution.reviews` placeholder)
  const [factors, setFactors] = useState<Array<{factor_id: string; name: string; description?: string; scope_type?: string}>>([]);
  const [factorRatings, setFactorRatings] = useState<Record<string, number>>({});
  const [aggregates, setAggregates] = useState<any>(null);
  const [reviewsList, setReviewsList] = useState<any[]>([]);
  const [segment, setSegment] = useState<'individual' | 'organization' | 'government'>('individual');
  const [subsegment, setSubsegment] = useState<string>('customer');
  const [reviewText, setReviewText] = useState('');
  const [reviewTitle, setReviewTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { fetchSolution(); }, [solution_id]);
  useEffect(() => {
    if (activeTab === 'reviews' && solution_id) {
      loadReviewNet();
    }
  }, [activeTab, solution_id]);

  const fetchSolution = async () => {
    try {
      const res = await api.get(`/solutions-store/solutions/${solution_id}`, {
        headers: { Authorization: `Bearer ${session}` },
      });
      setSolution(res.data);
    } catch (e: any) {
      console.error('Fetch error:', e);
      showAlert('Error', 'Failed to load solution');
    } finally {
      setLoading(false);
    }
  };

  const loadReviewNet = async () => {
    try {
      const [fRes, aRes, rRes] = await Promise.all([
        api.get(`/review-net/factors?solution_id=${solution_id}`),
        api.get(`/review-net/aggregates?solution_id=${solution_id}`),
        api.get(`/review-net/reviews?solution_id=${solution_id}`),
      ]);
      setFactors(fRes.data?.factors || []);
      setAggregates(aRes.data || null);
      setReviewsList(rRes.data?.items || []);
    } catch (e: any) {
      console.warn('ReviewNet load error:', e?.response?.data || e.message);
    }
  };

  const submitReview = async () => {
    const ratings = Object.fromEntries(Object.entries(factorRatings).filter(([_, v]) => v > 0));
    if (Object.keys(ratings).length === 0) {
      showAlert('Missing Ratings', 'Please rate at least one qualitative factor.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/review-net/reviews', {
        solution_id,
        reviewer_segment: segment,
        reviewer_subsegment: subsegment,
        factor_ratings: ratings,
        title: reviewTitle || undefined,
        comment: reviewText || undefined,
      });
      setShowReviewModal(false);
      setReviewText(''); setReviewTitle(''); setFactorRatings({});
      const status = res.data?.status;
      const message = status === 'auto_approved'
        ? 'Review auto-approved and published.'
        : status === 'pending'
        ? 'Review submitted — pending admin moderation.'
        : 'Review processed.';
      showAlert('Success', message);
      loadReviewNet();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to submit review';
      showAlert('Error', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  const voteHelpful = async (review_id: string, helpful: boolean) => {
    try {
      await api.post(`/review-net/reviews/${review_id}/helpful`, { helpful });
      loadReviewNet();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Vote failed';
      showAlert('Vote failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const renderStars = (rating: number) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      const filled = rating / 2 >= i;
      const half = rating / 2 >= i - 0.5 && !filled;
      stars.push(
        <Ionicons key={i} name={filled ? 'star' : half ? 'star-half' : 'star-outline'}
          size={16} color={COLORS.gold} />
      );
    }
    return <View style={{ flexDirection: 'row', gap: 1 }}>{stars}</View>;
  };

  const renderRatingSelector = (factor: string) => {
    const current = factorRatings[factor] || 0;
    return (
      <View style={styles.ratingRow} key={factor}>
        <Text style={styles.ratingLabel} numberOfLines={1}>{factor}</Text>
        <View style={styles.ratingDots}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
            <TouchableOpacity key={n} onPress={() => setFactorRatings(prev => ({ ...prev, [factor]: n }))}>
              <View style={[styles.ratingDot, current >= n && styles.ratingDotActive,
                current >= n && { backgroundColor: n <= 3 ? COLORS.danger : n <= 6 ? COLORS.warning : COLORS.accent }]}>
                <Text style={[styles.ratingDotText, current >= n && { color: '#FFF' }]}>{n}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  if (!solution) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={{ color: COLORS.text, textAlign: 'center', marginTop: 60 }}>Solution not found</Text>
      </SafeAreaView>
    );
  }

  const typeColor = TYPE_COLORS[solution.type] || COLORS.primary;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>{solution.name}</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabRow}>
        {(['overview', 'quantitative', 'reviews'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Ionicons name={tab === 'overview' ? 'information-circle' : tab === 'quantitative' ? 'bar-chart' : 'chatbubbles'} size={16}
              color={activeTab === tab ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === 'quantitative' ? 'Factors' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 100 }}>
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
            {/* Type & Status */}
            <View style={styles.badgeRow}>
              <View style={[styles.typeBadge, { backgroundColor: typeColor + '20' }]}>
                <Ionicons name={TYPE_ICONS[solution.type] as any} size={16} color={typeColor} />
                <Text style={[styles.badgeText, { color: typeColor }]}>{solution.type.replace('_', ' ')}</Text>
              </View>
              {solution.is_authorized && (
                <View style={[styles.typeBadge, { backgroundColor: COLORS.accent + '20' }]}>
                  <Ionicons name="shield-checkmark" size={14} color={COLORS.accent} />
                  <Text style={[styles.badgeText, { color: COLORS.accent }]}>Authorized</Text>
                </View>
              )}
              <View style={[styles.typeBadge, { backgroundColor: COLORS.surfaceLight }]}>
                <Ionicons name="location" size={14} color={COLORS.textMuted} />
                <Text style={[styles.badgeText, { color: COLORS.textMuted }]}>{solution.city || solution.country}</Text>
              </View>
            </View>

            {/* Description */}
            <Text style={styles.description}>{solution.description}</Text>

            {/* Provider & Price */}
            <View style={styles.infoCard}>
              {solution.provider && (
                <View style={styles.infoRow}>
                  <Ionicons name="business-outline" size={16} color={COLORS.textMuted} />
                  <Text style={styles.infoLabel}>Provider</Text>
                  <Text style={styles.infoValue}>{solution.provider}</Text>
                </View>
              )}
              {solution.price_range && (
                <View style={styles.infoRow}>
                  <Ionicons name="pricetag" size={16} color={COLORS.accent} />
                  <Text style={styles.infoLabel}>Price</Text>
                  <Text style={[styles.infoValue, { color: COLORS.accent }]}>{solution.price_range}</Text>
                </View>
              )}
              {solution.url && (
                <View style={styles.infoRow}>
                  <Ionicons name="link" size={16} color={COLORS.primary} />
                  <Text style={styles.infoLabel}>URL</Text>
                  <Text style={[styles.infoValue, { color: COLORS.primary }]} numberOfLines={1}>{solution.url}</Text>
                </View>
              )}
            </View>

            {/* Type-specific fields */}
            {solution.type_specific && Object.keys(solution.type_specific).length > 0 && (
              <View style={styles.infoCard}>
                <Text style={styles.sectionTitle}>Details</Text>
                {Object.entries(solution.type_specific).map(([key, val]) => (
                  <View style={styles.infoRow} key={key}>
                    <Ionicons name="chevron-forward" size={14} color={COLORS.textMuted} />
                    <Text style={styles.infoLabel}>{key.replace(/_/g, ' ')}</Text>
                    <Text style={styles.infoValue}>{String(val)}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Overall Rating */}
            {solution.overall_avg_rating && (
              <View style={styles.ratingCard}>
                <Text style={styles.bigRating}>{solution.overall_avg_rating}</Text>
                <Text style={styles.ratingMax}>/10</Text>
                {renderStars(solution.overall_avg_rating)}
                <Text style={styles.ratingCount}>
                  {solution.reviews?.length || 0} reviews
                </Text>
              </View>
            )}
          </>
        )}

        {/* Quantitative Factors Tab */}
        {activeTab === 'quantitative' && (
          <>
            <Text style={styles.sectionTitle}>Quantitative Factors</Text>
            <Text style={styles.sectionSubtitle}>Measurable data points for this solution</Text>
            {(solution.quantitative_factors || []).length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="analytics-outline" size={36} color={COLORS.textMuted} />
                <Text style={styles.emptyText}>No quantitative factors added yet</Text>
              </View>
            ) : (
              solution.quantitative_factors.map((f: any, i: number) => (
                <View style={styles.factorCard} key={i}>
                  <View style={styles.factorHeader}>
                    <Text style={styles.factorName}>{f.factor_name}</Text>
                    <View style={styles.factorValue}>
                      <Text style={styles.factorValueText}>{f.value}</Text>
                      <Text style={styles.factorUnit}>{f.unit}</Text>
                    </View>
                  </View>
                  {/* Visual bar */}
                  <View style={styles.factorBar}>
                    <View style={[styles.factorBarFill, { width: `${Math.min((typeof f.value === 'number' ? f.value : 50) / 100 * 100, 100)}%` }]} />
                  </View>
                </View>
              ))
            )}
          </>
        )}

        {/* Reviews Tab (ReviewNet v2) */}
        {activeTab === 'reviews' && (
          <>
            <View style={styles.reviewHeader}>
              <View>
                <Text style={styles.sectionTitle}>ReviewNet</Text>
                <Text style={styles.sectionSubtitle}>
                  {aggregates && aggregates.total_reviews > 0
                    ? `${aggregates.total_reviews} reviews • avg ${aggregates.overall?.average ?? 0}/5`
                    : 'Be the first to rate the qualitative factors'}
                </Text>
              </View>
              <TouchableOpacity testID="rn-add-review" style={styles.addReviewBtn} onPress={() => setShowReviewModal(true)}>
                <Ionicons name="add" size={16} color={COLORS.text} />
                <Text style={styles.addReviewText}>Add Review</Text>
              </TouchableOpacity>
            </View>

            {/* Per-segment aggregates */}
            {aggregates && Object.keys(aggregates.segments || {}).length > 0 && (
              <View style={styles.scoresCard}>
                <Text style={styles.scoresTitle}>By reviewer segment</Text>
                {(['individual', 'organization', 'government'] as const).map(seg => {
                  const sg = aggregates.segments?.[seg];
                  if (!sg || !sg.review_count) return null;
                  return (
                    <View key={seg} style={{ marginBottom: 8 }}>
                      <Text style={[styles.scoreName, { fontWeight: '700', color: COLORS.text }]}>
                        {seg.charAt(0).toUpperCase() + seg.slice(1)} · {sg.overall?.avg ?? 0}/5 ({sg.review_count})
                      </Text>
                    </View>
                  );
                })}
              </View>
            )}

            {/* Per-factor aggregates */}
            {aggregates && aggregates.overall?.per_factor && Object.keys(aggregates.overall.per_factor).length > 0 && (
              <View style={styles.scoresCard}>
                <Text style={styles.scoresTitle}>Per-factor average</Text>
                {factors.map(f => {
                  const a = aggregates.overall.per_factor[f.factor_id];
                  if (!a || !a.count) return null;
                  return (
                    <View key={f.factor_id} style={styles.scoreRow}>
                      <Text style={[styles.scoreName, { flex: 1 }]} numberOfLines={1}>{f.name}</Text>
                      <View style={styles.scoreBar}>
                        <View style={[styles.scoreBarFill, {
                          width: `${(a.avg / 5) * 100}%`,
                          backgroundColor: a.avg < 3 ? COLORS.danger : a.avg < 4 ? COLORS.warning : COLORS.accent,
                        }]} />
                      </View>
                      <Text style={styles.scoreValue}>{a.avg}/5</Text>
                    </View>
                  );
                })}
              </View>
            )}

            {/* Reviews list */}
            {reviewsList.length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="chatbubbles-outline" size={36} color={COLORS.textMuted} />
                <Text style={styles.emptyText}>No published reviews yet. Be the first!</Text>
              </View>
            ) : (
              reviewsList.map((rev: any) => (
                <View style={styles.reviewCard} key={rev.review_id}>
                  <View style={styles.reviewTop}>
                    <View style={styles.reviewerInfo}>
                      <View style={styles.avatarCircle}>
                        <Text style={styles.avatarText}>{(rev.reviewer_name || 'A')[0].toUpperCase()}</Text>
                      </View>
                      <View>
                        <Text style={styles.reviewerName}>
                          {rev.reviewer_name}
                          {rev.is_verified_buyer && <Text style={{ color: COLORS.accent }}> ✓ Verified</Text>}
                        </Text>
                        <Text style={styles.reviewDate}>
                          {new Date(rev.created_at).toLocaleDateString()} · {rev.reviewer_segment}{rev.reviewer_subsegment ? ` (${rev.reviewer_subsegment})` : ''}
                        </Text>
                      </View>
                    </View>
                    <View style={styles.reviewRatingBadge}>
                      <Text style={styles.reviewRatingNum}>{rev.overall_rating}</Text>
                      <Text style={styles.reviewRatingMax}>/5</Text>
                    </View>
                  </View>

                  {rev.title ? <Text style={[styles.reviewBody, { fontWeight: '700' }]}>{rev.title}</Text> : null}
                  {rev.comment ? <Text style={styles.reviewBody}>{rev.comment}</Text> : null}

                  {/* Factor ratings */}
                  {rev.factor_ratings && Object.keys(rev.factor_ratings).length > 0 && (
                    <View style={styles.reviewFactors}>
                      {Object.entries(rev.factor_ratings).map(([fid, rating]: any, i: number) => {
                        const factor = factors.find(f => f.factor_id === fid);
                        const label = factor?.name || fid.replace(/^qf_[a-z_]+_/, '').replace(/_/g, ' ');
                        const r = Number(rating);
                        return (
                          <View key={i} style={styles.reviewFactorChip}>
                            <Text style={styles.reviewFactorName} numberOfLines={1}>{label}</Text>
                            <Text style={[styles.reviewFactorScore, {
                              color: r <= 2 ? COLORS.danger : r <= 3 ? COLORS.warning : COLORS.accent,
                            }]}>{r}/5</Text>
                          </View>
                        );
                      })}
                    </View>
                  )}

                  {/* Owner reply */}
                  {rev.owner_reply && (
                    <View style={{ marginTop: 10, padding: 10, backgroundColor: COLORS.surfaceLight, borderRadius: 10, borderLeftWidth: 3, borderLeftColor: COLORS.primary }}>
                      <Text style={{ fontSize: 12, fontWeight: '700', color: COLORS.primary, marginBottom: 4 }}>
                        Owner reply · {rev.owner_reply.by_user_name}
                      </Text>
                      <Text style={{ fontSize: 13, color: COLORS.textSecondary }}>{rev.owner_reply.content}</Text>
                    </View>
                  )}

                  {/* Helpfulness */}
                  <View style={{ flexDirection: 'row', gap: 12, marginTop: 8 }}>
                    <TouchableOpacity onPress={() => voteHelpful(rev.review_id, true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                      <Ionicons name="thumbs-up-outline" size={14} color={COLORS.accent} />
                      <Text style={{ fontSize: 12, color: COLORS.textSecondary }}>{rev.helpful_yes_count || 0}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => voteHelpful(rev.review_id, false)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                      <Ionicons name="thumbs-down-outline" size={14} color={COLORS.danger} />
                      <Text style={{ fontSize: 12, color: COLORS.textSecondary }}>{rev.helpful_no_count || 0}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))
            )}
          </>
        )}
      </ScrollView>

      {/* Review Modal — ReviewNet v2 */}
      <Modal visible={showReviewModal} animationType="slide" transparent onRequestClose={() => setShowReviewModal(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Write a Review</Text>
                <TouchableOpacity onPress={() => setShowReviewModal(false)}>
                  <Ionicons name="close" size={24} color={COLORS.text} />
                </TouchableOpacity>
              </View>

              <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
                {/* Segment selector */}
                <Text style={styles.modalLabel}>I'm reviewing as</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
                  {(['individual', 'organization', 'government'] as const).map(s => (
                    <TouchableOpacity
                      key={s}
                      onPress={() => {
                        setSegment(s);
                        const subs = s === 'individual' ? 'customer'
                          : s === 'organization' ? 'business_corporate'
                          : 'regulator';
                        setSubsegment(subs);
                      }}
                      style={[
                        { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border },
                        segment === s && { backgroundColor: COLORS.primary + '30', borderColor: COLORS.primary },
                      ]}
                    >
                      <Text style={[{ fontSize: 12, color: COLORS.textSecondary, fontWeight: '600' }, segment === s && { color: COLORS.primary }]}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Sub-segment chips */}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                  {(segment === 'individual' ? ['customer', 'observer', 'expert']
                    : segment === 'organization' ? ['business_corporate', 'educational_institution', 'ngo_nonprofit']
                    : ['regulator', 'local_body', 'central_state_dept']
                  ).map(ss => (
                    <TouchableOpacity
                      key={ss}
                      onPress={() => setSubsegment(ss)}
                      style={[
                        { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, backgroundColor: COLORS.surfaceLight, borderWidth: 1, borderColor: COLORS.border },
                        subsegment === ss && { backgroundColor: COLORS.primary + '20', borderColor: COLORS.primary },
                      ]}
                    >
                      <Text style={[{ fontSize: 11, color: COLORS.textSecondary }, subsegment === ss && { color: COLORS.primary, fontWeight: '700' }]}>
                        {ss.replace(/_/g, ' ')}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <Text style={styles.modalLabel}>Rate Qualitative Factors (1-5 stars)</Text>
                {factors.length === 0 ? (
                  <Text style={{ color: COLORS.textMuted, fontSize: 12, marginVertical: 12 }}>Loading factors…</Text>
                ) : (
                  factors.map(f => (
                    <View key={f.factor_id} style={{ marginBottom: 12 }}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text style={{ color: COLORS.text, fontSize: 13, flex: 1 }}>{f.name}</Text>
                        <Text style={{ color: COLORS.textMuted, fontSize: 11 }}>{f.scope_type}</Text>
                      </View>
                      <View style={{ flexDirection: 'row', gap: 8 }}>
                        {[1, 2, 3, 4, 5].map(n => (
                          <TouchableOpacity
                            key={n}
                            testID={`rn-rate-${f.factor_id}-${n}`}
                            onPress={() => setFactorRatings({ ...factorRatings, [f.factor_id]: n })}
                          >
                            <Ionicons
                              name={(factorRatings[f.factor_id] || 0) >= n ? 'star' : 'star-outline'}
                              size={26}
                              color={(factorRatings[f.factor_id] || 0) >= n ? COLORS.gold : COLORS.textMuted}
                            />
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  ))
                )}

                <Text style={[styles.modalLabel, { marginTop: 8 }]}>Title (optional)</Text>
                <TextInput
                  testID="rn-title"
                  style={[styles.textArea, { height: 40 }]}
                  placeholder="Headline of your experience"
                  placeholderTextColor={COLORS.textMuted}
                  value={reviewTitle}
                  onChangeText={setReviewTitle}
                />

                <Text style={styles.modalLabel}>Your Review</Text>
                <TextInput
                  testID="rn-comment"
                  style={styles.textArea}
                  placeholder="Share your experience…"
                  placeholderTextColor={COLORS.textMuted}
                  value={reviewText}
                  onChangeText={setReviewText}
                  multiline
                  numberOfLines={4}
                />
              </ScrollView>

              <TouchableOpacity
                testID="rn-submit-review"
                style={[styles.submitBtn, submitting && { opacity: 0.6 }]}
                onPress={submitReview}
                disabled={submitting}
              >
                {submitting ? <ActivityIndicator color="#FFF" /> :
                  <Text style={styles.submitBtnText}>Submit Review</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 8, marginRight: 8 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  tabRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 10, borderRadius: 12, backgroundColor: COLORS.surface },
  tabActive: { backgroundColor: COLORS.primary + '20', borderWidth: 1, borderColor: COLORS.primary },
  tabText: { fontSize: 13, color: COLORS.textMuted, fontWeight: '500' },
  tabTextActive: { color: COLORS.primary },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  typeBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  badgeText: { fontSize: 12, fontWeight: '600' },
  description: { fontSize: 15, color: COLORS.textSecondary, lineHeight: 22, marginBottom: 16 },
  infoCard: { backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  infoLabel: { fontSize: 13, color: COLORS.textMuted, width: 80, textTransform: 'capitalize' },
  infoValue: { flex: 1, fontSize: 14, color: COLORS.text, fontWeight: '500' },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginBottom: 4 },
  sectionSubtitle: { fontSize: 13, color: COLORS.textMuted, marginBottom: 12 },
  ratingCard: { alignItems: 'center', backgroundColor: COLORS.surface, borderRadius: 16, padding: 20, borderWidth: 1, borderColor: COLORS.border, marginTop: 8 },
  bigRating: { fontSize: 48, fontWeight: '800', color: COLORS.gold },
  ratingMax: { fontSize: 16, color: COLORS.textMuted, marginTop: -8, marginBottom: 8 },
  ratingCount: { fontSize: 13, color: COLORS.textMuted, marginTop: 8 },
  factorCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  factorHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  factorName: { fontSize: 14, color: COLORS.text, fontWeight: '500', flex: 1 },
  factorValue: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  factorValueText: { fontSize: 18, fontWeight: '700', color: COLORS.primary },
  factorUnit: { fontSize: 12, color: COLORS.textMuted },
  factorBar: { height: 6, backgroundColor: COLORS.bg, borderRadius: 3, overflow: 'hidden' },
  factorBarFill: { height: '100%', backgroundColor: COLORS.primary, borderRadius: 3 },
  reviewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  addReviewBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20 },
  addReviewText: { fontSize: 13, color: COLORS.text, fontWeight: '600' },
  scoresCard: { backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  scoresTitle: { fontSize: 15, fontWeight: '600', color: COLORS.text, marginBottom: 12 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  scoreName: { fontSize: 12, color: COLORS.textSecondary, width: 100 },
  scoreBar: { flex: 1, height: 8, backgroundColor: COLORS.bg, borderRadius: 4, overflow: 'hidden' },
  scoreBarFill: { height: '100%', borderRadius: 4 },
  scoreValue: { fontSize: 12, fontWeight: '600', color: COLORS.text, width: 40, textAlign: 'right' },
  reviewCard: { backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  reviewTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  reviewerInfo: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatarCircle: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.primary + '30', alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 14, fontWeight: '700', color: COLORS.primary },
  reviewerName: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  reviewDate: { fontSize: 11, color: COLORS.textMuted },
  reviewRatingBadge: { flexDirection: 'row', alignItems: 'baseline' },
  reviewRatingNum: { fontSize: 24, fontWeight: '800', color: COLORS.gold },
  reviewRatingMax: { fontSize: 12, color: COLORS.textMuted },
  reviewBody: { fontSize: 14, color: COLORS.textSecondary, lineHeight: 20, marginBottom: 8 },
  prosConsRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  prosConsText: { fontSize: 12 },
  reviewFactors: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.border },
  reviewFactorChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.bg, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  reviewFactorName: { fontSize: 11, color: COLORS.textMuted },
  reviewFactorScore: { fontSize: 11, fontWeight: '700' },
  emptyState: { alignItems: 'center', paddingTop: 40 },
  emptyText: { fontSize: 14, color: COLORS.textMuted, marginTop: 8 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: COLORS.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  modalLabel: { fontSize: 14, fontWeight: '600', color: COLORS.text, marginBottom: 8 },
  ratingRow: { marginBottom: 10 },
  ratingLabel: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 4 },
  ratingDots: { flexDirection: 'row', gap: 4 },
  ratingDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.surface, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: COLORS.border },
  ratingDotActive: { borderColor: 'transparent' },
  ratingDotText: { fontSize: 11, color: COLORS.textMuted, fontWeight: '600' },
  textArea: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, color: COLORS.text, fontSize: 14, borderWidth: 1, borderColor: COLORS.border, height: 80, textAlignVertical: 'top', marginBottom: 12 },
  submitBtn: { backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  submitBtnText: { fontSize: 16, fontWeight: '700', color: COLORS.text },
});
