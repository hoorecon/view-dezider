/**
 * Review Net — user-facing entry (June 2026)
 *
 * Three tabs:
 *  1) Browse Solutions  → tap a solution → factor-wise rating + comment dialog
 *  2) My Reviews        → list of reviews I submitted (with status & moderation outcome)
 *  3) Top Rated         → solutions sorted by aggregate stars
 *
 * Submit flow follows the existing /api/review-net contract:
 *   • GET  /review-net/factors?life_area=X   → fetch qualitative factors
 *   • GET  /review-net/eligibility/{sid}     → can I review?
 *   • POST /review-net/reviews               → { solution_id, factor_ratings, comment, ... }
 *
 * Factor-wise averages also surface in MyDezider's assessment step later
 * (deep-link via /api/review-net/aggregates?solution_id=…).
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Platform, KeyboardAvoidingView, Pressable,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

type Tab = 'browse' | 'mine' | 'top';

interface Solution {
  solution_id: string;
  name: string;
  description?: string;
  life_area?: string;
  category?: string;
}

interface Factor {
  factor_id: string;
  name: string;
  slug: string;
  description?: string;
}

interface Review {
  review_id: string;
  solution_id: string;
  solution_name?: string;
  factor_ratings: Record<string, number>;
  comment?: string;
  title?: string;
  status?: string;          // pending / approved / auto_approved / rejected
  created_at?: string;
}

interface Aggregate {
  solution_id: string;
  total_reviews: number;
  overall: { average: number; count: number; per_factor: Record<string, { avg: number; count: number }> };
}

export default function ReviewNetPage() {
  const router = useRouter();
  const user = useAuthStore(s => s.user);
  const authReady = !!user;

  const [tab, setTab] = useState<Tab>('browse');
  const [loading, setLoading] = useState(true);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [aggregates, setAggregates] = useState<Record<string, Aggregate>>({});
  const [myReviews, setMyReviews] = useState<Review[]>([]);

  // Write-review modal state
  const [writeOpen, setWriteOpen] = useState(false);
  const [writeTarget, setWriteTarget] = useState<Solution | null>(null);
  const [factors, setFactors] = useState<Factor[]>([]);
  const [factorRatings, setFactorRatings] = useState<Record<string, number>>({});
  const [comment, setComment] = useState('');
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [eligibility, setEligibility] = useState<{ is_eligible: boolean; reason: string } | null>(null);

  // ============ LOAD ============
  const fetchSolutions = useCallback(async () => {
    try {
      const r = await api.get('/solutions-store/solutions', { params: { limit: 50 } });
      const arr = (r.data?.solutions || r.data || []) as Solution[];
      setSolutions(arr);
      // Pre-fetch aggregates in parallel for the top-rated tab
      const aggs: Record<string, Aggregate> = {};
      await Promise.all(
        arr.slice(0, 30).map(async s => {
          try {
            const a = await api.get('/review-net/aggregates', { params: { solution_id: s.solution_id } });
            aggs[s.solution_id] = a.data;
          } catch {/* silent */}
        })
      );
      setAggregates(aggs);
    } catch (e) {
      setSolutions([]);
    }
  }, []);

  const fetchMyReviews = useCallback(async () => {
    try {
      const r = await api.get('/review-net/reviews', { params: { mine: true } });
      const arr = (r.data?.reviews || r.data || []) as Review[];
      setMyReviews(arr);
    } catch {
      setMyReviews([]);
    }
  }, []);

  useEffect(() => {
    if (!authReady) return;
    (async () => {
      setLoading(true);
      await Promise.all([fetchSolutions(), fetchMyReviews()]);
      setLoading(false);
    })();
  }, [authReady, fetchSolutions, fetchMyReviews]);

  // ============ WRITE MODAL ============
  const openWriteModal = async (sol: Solution) => {
    setWriteTarget(sol);
    setComment('');
    setTitle('');
    setFactorRatings({});
    setEligibility(null);
    setWriteOpen(true);
    try {
      const [fRes, eRes] = await Promise.all([
        api.get('/review-net/factors', { params: { scope_type: 'global' } }),
        api.get(`/review-net/eligibility/${sol.solution_id}`),
      ]);
      setFactors((fRes.data?.factors || fRes.data || []) as Factor[]);
      setEligibility({ is_eligible: !!eRes.data?.is_eligible, reason: eRes.data?.reason || '' });
    } catch (e) {
      setFactors([]);
      setEligibility({ is_eligible: false, reason: 'Could not load review form. Try again.' });
    }
  };

  const setRating = (factorId: string, stars: number) =>
    setFactorRatings(p => ({ ...p, [factorId]: stars }));

  const submitReview = async () => {
    if (!writeTarget) return;
    if (Object.keys(factorRatings).length === 0) {
      return showAlert('Required', 'Tap at least one ⭐ to rate one factor.');
    }
    if (eligibility && !eligibility.is_eligible) {
      return showAlert('Not eligible', eligibility.reason || 'You can\'t review this solution.');
    }
    setSubmitting(true);
    try {
      await api.post('/review-net/reviews', {
        solution_id: writeTarget.solution_id,
        reviewer_segment: 'individual',
        factor_ratings: factorRatings,
        comment: comment.trim() || undefined,
        title: title.trim() || undefined,
      });
      showAlert('Thanks!', 'Your review was submitted. It will appear once approved by moderators (or auto-approved if no rules block it).');
      setWriteOpen(false);
      // Refresh local data
      await Promise.all([fetchMyReviews(), fetchSolutions()]);
    } catch (e: any) {
      showAlert('Submit failed', e?.response?.data?.detail || 'Try again');
    } finally { setSubmitting(false); }
  };

  // ============ HELPERS ============
  const renderStars = (n: number, onPress?: (v: number) => void, size = 22) => (
    <View style={{ flexDirection: 'row', gap: 2 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <TouchableOpacity key={i} onPress={onPress ? () => onPress(i) : undefined} disabled={!onPress} hitSlop={4}>
          <Ionicons
            name={n >= i ? 'star' : 'star-outline'}
            size={size}
            color={n >= i ? '#F59E0B' : '#CBD5E1'}
          />
        </TouchableOpacity>
      ))}
    </View>
  );

  const topRated = [...solutions]
    .map(s => ({ s, agg: aggregates[s.solution_id] }))
    .filter(x => x.agg && x.agg.total_reviews > 0)
    .sort((a, b) => (b.agg!.overall.average || 0) - (a.agg!.overall.average || 0))
    .slice(0, 20);

  // ============ RENDER ============
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#FBBF24']} style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.headerBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Review Net</Text>
          <Text style={s.headerSub}>Factor-wise reviews · powers decision assessment</Text>
        </View>
        <Ionicons name="star" size={22} color="#FFF" />
      </LinearGradient>

      {/* Tab bar */}
      <View style={s.tabbar}>
        {(['browse', 'mine', 'top'] as Tab[]).map(t => (
          <TouchableOpacity key={t} style={[s.tab, tab === t && s.tabActive]} onPress={() => setTab(t)}>
            <Text style={[s.tabText, tab === t && s.tabTextActive]}>
              {t === 'browse' ? 'Browse Solutions' : t === 'mine' ? `My Reviews (${myReviews.length})` : 'Top Rated'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#F59E0B" style={{ marginTop: 60 }} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
          {tab === 'browse' && (
            <>
              {solutions.length === 0 ? (
                <Text style={s.empty}>No solutions available to review yet.</Text>
              ) : solutions.map(sol => {
                const agg = aggregates[sol.solution_id];
                return (
                  <View key={sol.solution_id} style={s.card}>
                    <View style={s.cardHeader}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.cardTitle} numberOfLines={2}>{sol.name}</Text>
                        {sol.description ? <Text style={s.cardSub} numberOfLines={2}>{sol.description}</Text> : null}
                      </View>
                      {agg && agg.total_reviews > 0 ? (
                        <View style={s.aggBadge}>
                          {renderStars(Math.round(agg.overall.average), undefined, 12)}
                          <Text style={s.aggBadgeText}>{agg.overall.average.toFixed(1)} · {agg.total_reviews}</Text>
                        </View>
                      ) : (
                        <Text style={s.noReviews}>No reviews yet</Text>
                      )}
                    </View>
                    <TouchableOpacity style={s.writeBtn} onPress={() => openWriteModal(sol)}>
                      <Ionicons name="create" size={14} color="#FFF" />
                      <Text style={s.writeBtnText}>Write a review</Text>
                    </TouchableOpacity>
                  </View>
                );
              })}
            </>
          )}

          {tab === 'mine' && (
            <>
              {myReviews.length === 0 ? (
                <Text style={s.empty}>You haven't reviewed anything yet. Switch to <Text style={{ fontWeight: '700' }}>Browse Solutions</Text> and rate one.</Text>
              ) : myReviews.map(r => (
                <View key={r.review_id} style={s.card}>
                  <View style={s.cardHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.cardTitle} numberOfLines={2}>{r.solution_name || r.solution_id}</Text>
                      {r.title ? <Text style={s.cardSub} numberOfLines={1}>{r.title}</Text> : null}
                    </View>
                    <View style={[s.statusPill, r.status === 'rejected' && { backgroundColor: '#FEE2E2', borderColor: '#FCA5A5' }, r.status === 'approved' && { backgroundColor: '#D1FAE5', borderColor: '#6EE7B7' }]}>
                      <Text style={s.statusPillText}>{(r.status || 'pending').replace('_', ' ')}</Text>
                    </View>
                  </View>
                  {r.comment ? <Text style={s.comment}>{r.comment}</Text> : null}
                  <View style={s.factorRow}>
                    {Object.entries(r.factor_ratings || {}).map(([fid, rating]) => (
                      <View key={fid} style={s.factorChip}>
                        <Text style={s.factorChipName}>{fid.slice(0, 12)}</Text>
                        <Text style={s.factorChipRating}>{rating}★</Text>
                      </View>
                    ))}
                  </View>
                </View>
              ))}
            </>
          )}

          {tab === 'top' && (
            <>
              {topRated.length === 0 ? (
                <Text style={s.empty}>No rated solutions yet. Be the first to leave a review!</Text>
              ) : topRated.map(({ s: sol, agg }, idx) => (
                <View key={sol.solution_id} style={s.card}>
                  <View style={s.cardHeader}>
                    <View style={s.rankBadge}><Text style={s.rankBadgeText}>{idx + 1}</Text></View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.cardTitle} numberOfLines={2}>{sol.name}</Text>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
                        {renderStars(Math.round(agg!.overall.average), undefined, 13)}
                        <Text style={s.cardSub}>{agg!.overall.average.toFixed(1)} · {agg!.total_reviews} reviews</Text>
                      </View>
                    </View>
                    <TouchableOpacity onPress={() => openWriteModal(sol)} hitSlop={6}>
                      <Ionicons name="add-circle" size={22} color="#F59E0B" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </>
          )}
        </ScrollView>
      )}

      {/* WRITE-REVIEW MODAL */}
      <Modal visible={writeOpen} transparent animationType="fade" onRequestClose={() => setWriteOpen(false)}>
        <Pressable style={s.backdrop} onPress={() => setWriteOpen(false)}>
          <Pressable style={s.sheet} onPress={e => e.stopPropagation()}>
            <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
              <View style={s.modalHeader}>
                <Text style={s.modalTitle}>Review · {writeTarget?.name}</Text>
                <TouchableOpacity onPress={() => setWriteOpen(false)} hitSlop={8}>
                  <Ionicons name="close" size={22} color="#94A3B8" />
                </TouchableOpacity>
              </View>
              {eligibility && !eligibility.is_eligible && (
                <View style={s.ineligible}>
                  <Ionicons name="lock-closed" size={14} color="#B91C1C" />
                  <Text style={s.ineligibleText}>{eligibility.reason || 'Not eligible to review this solution.'}</Text>
                </View>
              )}
              <ScrollView style={{ maxHeight: 460 }} contentContainerStyle={{ paddingBottom: 14 }}>
                <Text style={s.fieldLabel}>Optional title</Text>
                <TextInput
                  style={s.input}
                  placeholder="e.g. 'Solid value for the price'"
                  placeholderTextColor="#9CA3AF"
                  value={title}
                  onChangeText={setTitle}
                  maxLength={120}
                />
                <Text style={[s.fieldLabel, { marginTop: 12 }]}>Rate each subjective factor</Text>
                {factors.length === 0 ? (
                  <Text style={s.empty}>No factors configured yet. Ask admin to seed factors in /admin/review-net.</Text>
                ) : factors.map(f => (
                  <View key={f.factor_id} style={s.factorEditRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.factorEditName}>{f.name}</Text>
                      {f.description ? <Text style={s.factorEditDesc} numberOfLines={2}>{f.description}</Text> : null}
                    </View>
                    {renderStars(factorRatings[f.factor_id] || 0, v => setRating(f.factor_id, v))}
                  </View>
                ))}
                <Text style={[s.fieldLabel, { marginTop: 12 }]}>Comment (optional)</Text>
                <TextInput
                  style={[s.input, { minHeight: 70, textAlignVertical: 'top' }]}
                  placeholder="Share specifics — what worked, what didn't, who would benefit most."
                  placeholderTextColor="#9CA3AF"
                  value={comment}
                  onChangeText={setComment}
                  multiline
                  maxLength={2000}
                />
              </ScrollView>
              <TouchableOpacity
                style={[s.submitBtn, (submitting || (eligibility && !eligibility.is_eligible)) && { opacity: 0.5 }]}
                onPress={submitReview}
                disabled={submitting || (eligibility && !eligibility.is_eligible)}
              >
                {submitting
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <>
                      <Ionicons name="paper-plane" size={14} color="#FFF" />
                      <Text style={s.submitBtnText}>Submit review</Text>
                    </>}
              </TouchableOpacity>
            </KeyboardAvoidingView>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 12 },
  headerBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.22)', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#FFF', fontSize: 17, fontWeight: '800' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 11, marginTop: 2 },

  tabbar: { flexDirection: 'row', backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#F1F5F9', paddingHorizontal: 8 },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabActive: { borderBottomColor: '#F59E0B' },
  tabText: { fontSize: 12, fontWeight: '600', color: '#64748B' },
  tabTextActive: { color: '#0F172A', fontWeight: '800' },

  empty: { fontSize: 13, color: '#94A3B8', textAlign: 'center', padding: 24, fontStyle: 'italic' },

  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#F1F5F9' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  cardSub: { fontSize: 11, color: '#64748B', marginTop: 2 },
  aggBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10, backgroundColor: '#FEF3C7', borderWidth: 1, borderColor: '#FCD34D' },
  aggBadgeText: { fontSize: 10, fontWeight: '800', color: '#92400E' },
  noReviews: { fontSize: 10, color: '#94A3B8', fontStyle: 'italic' },
  rankBadge: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center' },
  rankBadgeText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
  writeBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, backgroundColor: '#F59E0B' },
  writeBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  comment: { fontSize: 12, color: '#475569', marginVertical: 6, lineHeight: 17 },
  factorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  factorChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 8, backgroundColor: '#FEF3C7' },
  factorChipName: { fontSize: 9, fontWeight: '600', color: '#92400E' },
  factorChipRating: { fontSize: 9, fontWeight: '800', color: '#92400E' },
  statusPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, backgroundColor: '#FEF3C7', borderWidth: 1, borderColor: '#FCD34D' },
  statusPillText: { fontSize: 9, fontWeight: '800', color: '#92400E', textTransform: 'capitalize' },

  // Modal
  backdrop: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  sheet: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, width: '100%', maxWidth: 520 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', flex: 1, marginRight: 8 },
  ineligible: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FEE2E2', borderRadius: 8, padding: 8, marginVertical: 8 },
  ineligibleText: { fontSize: 11, color: '#B91C1C', flex: 1 },
  fieldLabel: { fontSize: 11, fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  factorEditRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, gap: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  factorEditName: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  factorEditDesc: { fontSize: 11, color: '#64748B', marginTop: 1 },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#F59E0B', borderRadius: 10, paddingVertical: 12, marginTop: 8 },
  submitBtnText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
});
