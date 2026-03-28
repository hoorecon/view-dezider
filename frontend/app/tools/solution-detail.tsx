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

  // Review form state
  const [reviewText, setReviewText] = useState('');
  const [reviewPros, setReviewPros] = useState('');
  const [reviewCons, setReviewCons] = useState('');
  const [factorRatings, setFactorRatings] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchSolution();
  }, [solution_id]);

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

  const submitReview = async () => {
    const qualitative_factors = Object.entries(factorRatings)
      .filter(([_, v]) => v > 0)
      .map(([k, v]) => ({ factor_name: k, rating: v, comment: '' }));

    if (qualitative_factors.length === 0) {
      showAlert('Missing Ratings', 'Please rate at least one qualitative factor.');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/reviewnet/reviews', {
        solution_id,
        qualitative_factors,
        review_text: reviewText,
        pros: reviewPros.split('\n').filter(Boolean),
        cons: reviewCons.split('\n').filter(Boolean),
      }, { headers: { Authorization: `Bearer ${session}` } });

      setShowReviewModal(false);
      setReviewText('');
      setReviewPros('');
      setReviewCons('');
      setFactorRatings({});
      fetchSolution(); // Refresh
      showAlert('Success', 'Review submitted!');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to submit review';
      showAlert('Error', msg);
    } finally {
      setSubmitting(false);
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

        {/* Reviews Tab (ReviewNet) */}
        {activeTab === 'reviews' && (
          <>
            <View style={styles.reviewHeader}>
              <View>
                <Text style={styles.sectionTitle}>ReviewNet</Text>
                <Text style={styles.sectionSubtitle}>Qualitative ratings & reviews</Text>
              </View>
              <TouchableOpacity style={styles.addReviewBtn} onPress={() => setShowReviewModal(true)}>
                <Ionicons name="add" size={16} color={COLORS.text} />
                <Text style={styles.addReviewText}>Add Review</Text>
              </TouchableOpacity>
            </View>

            {/* Aggregated Quality Scores */}
            {(solution.quality_scores || []).length > 0 && (
              <View style={styles.scoresCard}>
                <Text style={styles.scoresTitle}>Quality Scores</Text>
                {solution.quality_scores.map((qs: any, i: number) => (
                  <View style={styles.scoreRow} key={i}>
                    <Text style={styles.scoreName}>{qs.factor_name}</Text>
                    <View style={styles.scoreBar}>
                      <View style={[styles.scoreBarFill, { width: `${qs.avg_rating * 10}%`,
                        backgroundColor: qs.avg_rating <= 3 ? COLORS.danger : qs.avg_rating <= 6 ? COLORS.warning : COLORS.accent }]} />
                    </View>
                    <Text style={styles.scoreValue}>{qs.avg_rating}/10</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Individual Reviews */}
            {(solution.reviews || []).length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="chatbubbles-outline" size={36} color={COLORS.textMuted} />
                <Text style={styles.emptyText}>No reviews yet. Be the first!</Text>
              </View>
            ) : (
              solution.reviews.map((rev: any) => (
                <View style={styles.reviewCard} key={rev.review_id}>
                  <View style={styles.reviewTop}>
                    <View style={styles.reviewerInfo}>
                      <View style={styles.avatarCircle}>
                        <Text style={styles.avatarText}>{(rev.reviewer_name || 'A')[0].toUpperCase()}</Text>
                      </View>
                      <View>
                        <Text style={styles.reviewerName}>{rev.reviewer_name}</Text>
                        <Text style={styles.reviewDate}>{new Date(rev.created_at).toLocaleDateString()}</Text>
                      </View>
                    </View>
                    <View style={styles.reviewRatingBadge}>
                      <Text style={styles.reviewRatingNum}>{rev.overall_rating}</Text>
                      <Text style={styles.reviewRatingMax}>/10</Text>
                    </View>
                  </View>

                  {rev.review_text && <Text style={styles.reviewBody}>{rev.review_text}</Text>}

                  {rev.pros?.length > 0 && (
                    <View style={styles.prosConsRow}>
                      <Ionicons name="thumbs-up" size={14} color={COLORS.accent} />
                      <Text style={[styles.prosConsText, { color: COLORS.accent }]}>{rev.pros.join(', ')}</Text>
                    </View>
                  )}
                  {rev.cons?.length > 0 && (
                    <View style={styles.prosConsRow}>
                      <Ionicons name="thumbs-down" size={14} color={COLORS.danger} />
                      <Text style={[styles.prosConsText, { color: COLORS.danger }]}>{rev.cons.join(', ')}</Text>
                    </View>
                  )}

                  {/* Factor ratings */}
                  {rev.qualitative_factors?.length > 0 && (
                    <View style={styles.reviewFactors}>
                      {rev.qualitative_factors.map((qf: any, i: number) => (
                        <View style={styles.reviewFactorChip} key={i}>
                          <Text style={styles.reviewFactorName}>{qf.factor_name}</Text>
                          <Text style={[styles.reviewFactorScore, {
                            color: qf.rating <= 3 ? COLORS.danger : qf.rating <= 6 ? COLORS.warning : COLORS.accent
                          }]}>{qf.rating}/10</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              ))
            )}
          </>
        )}
      </ScrollView>

      {/* Review Modal */}
      <Modal visible={showReviewModal} animationType="slide" transparent>
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
                <Text style={styles.modalLabel}>Rate Qualitative Factors</Text>
                {DEFAULT_FACTORS.map(f => renderRatingSelector(f))}

                <Text style={[styles.modalLabel, { marginTop: 16 }]}>Your Review</Text>
                <TextInput
                  style={styles.textArea}
                  placeholder="Share your experience..."
                  placeholderTextColor={COLORS.textMuted}
                  value={reviewText}
                  onChangeText={setReviewText}
                  multiline
                  numberOfLines={3}
                />

                <Text style={styles.modalLabel}>Pros (one per line)</Text>
                <TextInput
                  style={[styles.textArea, { height: 60 }]}
                  placeholder="Good things..."
                  placeholderTextColor={COLORS.textMuted}
                  value={reviewPros}
                  onChangeText={setReviewPros}
                  multiline
                />

                <Text style={styles.modalLabel}>Cons (one per line)</Text>
                <TextInput
                  style={[styles.textArea, { height: 60 }]}
                  placeholder="Areas for improvement..."
                  placeholderTextColor={COLORS.textMuted}
                  value={reviewCons}
                  onChangeText={setReviewCons}
                  multiline
                />
              </ScrollView>

              <TouchableOpacity
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
