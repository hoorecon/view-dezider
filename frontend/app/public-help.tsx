/**
 * Public Help Feed (Collaboration Epic Phase C).
 * Browse open community help requests, view a request + its snapshot, contribute
 * suggestions, and (as owner) review/accept/dismiss contributions, close the
 * request, and merge accepted suggestions back into the decision.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, FlatList, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

interface Post {
  post_id: string; decision_id: string; owner_id: string; owner_name: string;
  step_number: number; step_name: string; title: string; context?: string;
  ask_message?: string; status: string; contribution_count: number; accepted_count: number;
  snapshot?: { factors?: any[]; options?: any[] }; created_at: string;
}

export default function PublicHelpScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ post?: string }>();
  const [tab, setTab] = useState<'feed' | 'mine'>('feed');
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');

  // detail modal
  const [active, setActive] = useState<Post | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [contribBody, setContribBody] = useState('');
  const [suggInput, setSuggInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = tab === 'mine' ? '/public-help/mine'
        : `/public-help/feed${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''}`;
      const r = await api.get(url);
      setPosts(r.data?.items || []);
    } catch { setPosts([]); }
    finally { setLoading(false); }
  }, [tab, search]);

  useEffect(() => { load(); }, [load]);

  // deep link ?post=ID
  useEffect(() => {
    if (params.post) openDetailById(String(params.post));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.post]);

  const openDetailById = async (postId: string) => {
    setDetailLoading(true);
    setActive({ post_id: postId } as Post);
    try {
      const r = await api.get(`/public-help/${postId}`);
      setDetail(r.data); setActive(r.data.post);
    } catch { showAlert('Error', 'Could not load request'); setActive(null); }
    finally { setDetailLoading(false); }
  };
  const openDetail = (p: Post) => openDetailById(p.post_id);
  const closeDetail = () => { setActive(null); setDetail(null); setContribBody(''); setSuggestions([]); setSuggInput(''); };
  const reloadDetail = async () => { if (active) { const r = await api.get(`/public-help/${active.post_id}`); setDetail(r.data); setActive(r.data.post); } };

  const addSugg = () => {
    const v = suggInput.trim();
    if (v && !suggestions.includes(v)) { setSuggestions([...suggestions, v]); setSuggInput(''); }
  };

  const submitContribution = async () => {
    if (!contribBody.trim() && suggestions.length === 0) { showAlert('Add input', 'Write a note or add at least one suggestion.'); return; }
    setBusy(true);
    try {
      await api.post(`/public-help/${active!.post_id}/contribute`, { body: contribBody.trim(), suggestions });
      setContribBody(''); setSuggestions([]); setSuggInput('');
      await reloadDetail(); load();
      showAlert('Thank you!', 'Your contribution was submitted.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed to submit'); }
    finally { setBusy(false); }
  };

  const review = async (cid: string, action: 'accept' | 'dismiss') => {
    setBusy(true);
    try { await api.post(`/public-help/contributions/${cid}/${action}`); await reloadDetail(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  const rateContribution = async (cid: string, stars: number) => {
    try {
      const r = await api.post(`/karma/rate/contribution/${cid}`, { stars });
      showAlert('Rated', r.data.karma_awarded ? `Awarded ${r.data.karma_awarded} karma to the contributor.` : 'Rating saved.');
      reloadDetail();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  const closeRequest = async () => {
    setBusy(true);
    try { await api.post(`/public-help/${active!.post_id}/close`); await reloadDetail(); load(); }
    catch { showAlert('Error', 'Failed to close'); }
    finally { setBusy(false); }
  };

  const mergeAccepted = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/public-help/${active!.post_id}/merge-accepted`);
      showAlert('Merged', `Added ${r.data.added} ${r.data.merged_as} to your decision.`);
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Nothing to merge'); }
    finally { setBusy(false); }
  };

  const isOwner = detail?.is_owner;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#0EA5E9', '#0369A1']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Public Help</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>

      <View style={styles.tabRow}>
        {(['feed', 'mine'] as const).map(t => (
          <TouchableOpacity key={t} style={[styles.tab, tab === t && styles.tabActive]} onPress={() => setTab(t)}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t === 'feed' ? 'Community Feed' : 'My Requests'}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {tab === 'feed' && (
        <View style={styles.searchRow}>
          <Ionicons name="search" size={16} color="#94A3B8" />
          <TextInput style={styles.searchInput} placeholder="Search requests…" value={search} onChangeText={setSearch} returnKeyType="search" onSubmitEditing={load} />
        </View>
      )}

      {loading ? (
        <ActivityIndicator style={{ marginTop: 40 }} color="#0EA5E9" />
      ) : (
        <FlatList
          data={posts}
          keyExtractor={(i) => i.post_id}
          contentContainerStyle={{ padding: 14, paddingBottom: 60 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="megaphone-outline" size={46} color="#BAE6FD" />
              <Text style={styles.emptyTitle}>{tab === 'mine' ? 'No requests yet' : 'No open requests'}</Text>
              <Text style={styles.emptyDesc}>{tab === 'mine'
                ? 'Open a decision step and tap “Ask the public for help” to publish a request here.'
                : 'When people ask the community for help on a decision step, it appears here for you to contribute.'}</Text>
            </View>
          }
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.card} onPress={() => openDetail(item)} activeOpacity={0.85}>
              <View style={styles.cardTopRow}>
                <View style={styles.stepBadge}><Text style={styles.stepBadgeText}>Step {item.step_number}</Text></View>
                <Text style={styles.stepName}>{item.step_name}</Text>
                {item.status !== 'open' && <View style={styles.closedBadge}><Text style={styles.closedText}>Closed</Text></View>}
              </View>
              <Text style={styles.cardTitle} numberOfLines={2}>{item.title || 'Untitled decision'}</Text>
              {!!item.ask_message && <Text style={styles.cardAsk} numberOfLines={2}>“{item.ask_message}”</Text>}
              <View style={styles.cardMeta}>
                <Text style={styles.metaText}>by {item.owner_name}</Text>
                <Text style={styles.metaDot}>·</Text>
                <Ionicons name="chatbubble-ellipses-outline" size={13} color="#64748B" />
                <Text style={styles.metaText}>{item.contribution_count} contribution{item.contribution_count === 1 ? '' : 's'}</Text>
                {item.accepted_count > 0 && <><Text style={styles.metaDot}>·</Text><Text style={[styles.metaText, { color: '#16A34A' }]}>{item.accepted_count} accepted</Text></>}
              </View>
            </TouchableOpacity>
          )}
        />
      )}

      {/* ---- Detail modal ---- */}
      <Modal visible={!!active} transparent animationType="slide" onRequestClose={closeDetail}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle} numberOfLines={1}>{active?.title || 'Help request'}</Text>
              <TouchableOpacity onPress={closeDetail}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            {detailLoading || !detail ? (
              <ActivityIndicator style={{ marginVertical: 40 }} color="#0EA5E9" />
            ) : (
              <ScrollView style={{ maxHeight: '90%' }} showsVerticalScrollIndicator={false}>
                <View style={styles.detailMetaRow}>
                  <View style={styles.stepBadge}><Text style={styles.stepBadgeText}>Step {active?.step_number}</Text></View>
                  <Text style={styles.stepName}>{active?.step_name}</Text>
                  {active?.status !== 'open' && <View style={styles.closedBadge}><Text style={styles.closedText}>Closed</Text></View>}
                </View>
                {!!active?.ask_message && <Text style={styles.detailAsk}>“{active.ask_message}”</Text>}
                {!!active?.context && <Text style={styles.detailContext}>{active.context}</Text>}

                {/* snapshot */}
                {(active?.snapshot?.factors?.length || active?.snapshot?.options?.length) ? (
                  <View style={styles.snapshot}>
                    <Text style={styles.snapTitle}>Current state</Text>
                    {!!active?.snapshot?.factors?.length && (
                      <Text style={styles.snapLine}>🏷 Factors: {active.snapshot.factors.map((f: any) => f.name).join(', ')}</Text>
                    )}
                    {!!active?.snapshot?.options?.length && (
                      <Text style={styles.snapLine}>🔘 Options: {active.snapshot.options.map((o: any) => o.name).join(', ')}</Text>
                    )}
                  </View>
                ) : null}

                {/* contribute (non-owner, open) */}
                {!isOwner && active?.status === 'open' && (
                  <View style={styles.contribBox}>
                    <Text style={styles.contribTitle}>Add your input</Text>
                    <TextInput style={styles.noteInput} value={contribBody} onChangeText={setContribBody} placeholder="Share advice, perspective, or experience…" multiline />
                    <View style={styles.suggRow}>
                      <TextInput style={styles.suggInput} value={suggInput} onChangeText={setSuggInput} placeholder={active.step_number >= 6 && active.step_number <= 7 ? 'Suggest an option…' : 'Suggest a factor…'} onSubmitEditing={addSugg} />
                      <TouchableOpacity style={styles.suggAdd} onPress={addSugg}><Ionicons name="add" size={20} color="#FFF" /></TouchableOpacity>
                    </View>
                    {suggestions.length > 0 && (
                      <View style={styles.chips}>
                        {suggestions.map(s => (
                          <View key={s} style={styles.chip}>
                            <Text style={styles.chipText}>{s}</Text>
                            <TouchableOpacity onPress={() => setSuggestions(suggestions.filter(x => x !== s))}><Ionicons name="close-circle" size={15} color="#0369A1" /></TouchableOpacity>
                          </View>
                        ))}
                      </View>
                    )}
                    <TouchableOpacity style={styles.submitBtn} onPress={submitContribution} disabled={busy}>
                      {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitText}>Submit contribution</Text>}
                    </TouchableOpacity>
                  </View>
                )}

                {/* owner controls */}
                {isOwner && (
                  <View style={styles.ownerBar}>
                    {active?.status === 'open' && (
                      <TouchableOpacity style={styles.ownerBtnGhost} onPress={closeRequest} disabled={busy}>
                        <Ionicons name="lock-closed-outline" size={15} color="#64748B" /><Text style={styles.ownerBtnGhostText}>Close</Text>
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity style={styles.ownerBtn} onPress={mergeAccepted} disabled={busy}>
                      <Ionicons name="git-merge-outline" size={15} color="#FFF" /><Text style={styles.ownerBtnText}>Merge accepted</Text>
                    </TouchableOpacity>
                  </View>
                )}

                {/* contributions list */}
                <Text style={styles.contribListTitle}>Contributions ({detail.contributions.length})</Text>
                {detail.contributions.length === 0 && <Text style={styles.noContrib}>No contributions yet.</Text>}
                {detail.contributions.map((c: any) => (
                  <View key={c.contribution_id} style={[styles.contribCard, c.status === 'accepted' && styles.contribAccepted, c.status === 'dismissed' && { opacity: 0.5 }]}>
                    <View style={styles.contribHead}>
                      <Text style={styles.contribName}>{c.contributor_name}{c.is_mine ? ' (you)' : ''}</Text>
                      <View style={[styles.statusPill,
                        c.status === 'accepted' && { backgroundColor: '#DCFCE7' },
                        c.status === 'dismissed' && { backgroundColor: '#FEE2E2' }]}>
                        <Text style={[styles.statusPillText,
                          c.status === 'accepted' && { color: '#16A34A' },
                          c.status === 'dismissed' && { color: '#B91C1C' }]}>{c.status}</Text>
                      </View>
                    </View>
                    {!!c.body && <Text style={styles.contribBody}>{c.body}</Text>}
                    {!!(c.suggestions || []).length && (
                      <View style={styles.chips}>
                        {c.suggestions.map((s: string, i: number) => (
                          <View key={i} style={styles.suggChip}><Text style={styles.suggChipText}>{s}</Text></View>
                        ))}
                      </View>
                    )}
                    {isOwner && c.status === 'pending' && (
                      <View style={styles.reviewRow}>
                        <TouchableOpacity style={styles.acceptBtn} onPress={() => review(c.contribution_id, 'accept')} disabled={busy}>
                          <Ionicons name="checkmark" size={14} color="#FFF" /><Text style={styles.acceptText}>Accept</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.dismissBtn} onPress={() => review(c.contribution_id, 'dismiss')} disabled={busy}>
                          <Ionicons name="close" size={14} color="#64748B" /><Text style={styles.dismissText}>Dismiss</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                    {isOwner && c.status === 'accepted' && (
                      <View style={styles.rateRow}>
                        <Text style={styles.rateLabel}>Rate this input{c.rating_avg != null ? ` (${c.rating_avg}★)` : ''}:</Text>
                        {[1, 2, 3, 4, 5].map(s => (
                          <TouchableOpacity key={s} onPress={() => rateContribution(c.contribution_id, s)}>
                            <Ionicons name={(c.rating_avg || 0) >= s ? 'star' : 'star-outline'} size={20} color="#F59E0B" />
                          </TouchableOpacity>
                        ))}
                      </View>
                    )}
                  </View>
                ))}
                <View style={{ height: 30 }} />
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  tabRow: { flexDirection: 'row', gap: 8, padding: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  tab: { flex: 1, paddingVertical: 9, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  tabActive: { backgroundColor: '#0EA5E9' },
  tabText: { fontSize: 13, fontWeight: '700', color: '#475569' },
  tabTextActive: { color: '#FFF' },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, margin: 12, marginBottom: 0, paddingHorizontal: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  empty: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: '#0F172A' },
  emptyDesc: { fontSize: 13, color: '#64748B', textAlign: 'center', paddingHorizontal: 28, lineHeight: 18 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#EEF2F7' },
  cardTopRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  stepBadge: { backgroundColor: '#E0F2FE', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  stepBadgeText: { fontSize: 10.5, fontWeight: '800', color: '#0369A1' },
  stepName: { fontSize: 12, fontWeight: '600', color: '#64748B', flex: 1 },
  closedBadge: { backgroundColor: '#F1F5F9', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  closedText: { fontSize: 10, fontWeight: '700', color: '#94A3B8' },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  cardAsk: { fontSize: 13, color: '#475569', fontStyle: 'italic', marginTop: 4 },
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8 },
  metaText: { fontSize: 11.5, color: '#64748B' },
  metaDot: { color: '#CBD5E1' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '92%' },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A', flex: 1, marginRight: 8 },
  detailMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  detailAsk: { fontSize: 14, color: '#0369A1', fontStyle: 'italic', backgroundColor: '#F0F9FF', borderRadius: 10, padding: 12, marginBottom: 10 },
  detailContext: { fontSize: 13, color: '#475569', lineHeight: 19, marginBottom: 10 },
  snapshot: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  snapTitle: { fontSize: 12, fontWeight: '800', color: '#475569', marginBottom: 5 },
  snapLine: { fontSize: 12.5, color: '#334155', marginTop: 3, lineHeight: 18 },
  contribBox: { backgroundColor: '#F0F9FF', borderRadius: 12, padding: 12, marginBottom: 14 },
  contribTitle: { fontSize: 14, fontWeight: '800', color: '#0369A1', marginBottom: 8 },
  noteInput: { borderWidth: 1, borderColor: '#BAE6FD', borderRadius: 10, padding: 10, fontSize: 13.5, color: '#0F172A', backgroundColor: '#FFF', minHeight: 70, textAlignVertical: 'top', marginBottom: 8 },
  suggRow: { flexDirection: 'row', gap: 8 },
  suggInput: { flex: 1, borderWidth: 1, borderColor: '#BAE6FD', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 9, fontSize: 13.5, color: '#0F172A', backgroundColor: '#FFF' },
  suggAdd: { width: 42, height: 40, borderRadius: 10, backgroundColor: '#0EA5E9', alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#E0F2FE', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14 },
  chipText: { fontSize: 12, color: '#0369A1', fontWeight: '600' },
  submitBtn: { backgroundColor: '#0EA5E9', paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginTop: 10 },
  submitText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  ownerBar: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  ownerBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#0369A1', paddingVertical: 11, borderRadius: 10 },
  ownerBtnText: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  ownerBtnGhost: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#F1F5F9', paddingVertical: 11, paddingHorizontal: 16, borderRadius: 10 },
  ownerBtnGhostText: { color: '#64748B', fontWeight: '700', fontSize: 13 },
  contribListTitle: { fontSize: 14, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  noContrib: { fontSize: 13, color: '#94A3B8', marginBottom: 10 },
  contribCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  contribAccepted: { borderColor: '#86EFAC', backgroundColor: '#F0FDF4' },
  contribHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  contribName: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  statusPill: { backgroundColor: '#F1F5F9', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  statusPillText: { fontSize: 10, fontWeight: '700', color: '#64748B', textTransform: 'capitalize' },
  contribBody: { fontSize: 13, color: '#334155', lineHeight: 19, marginTop: 2 },
  suggChip: { backgroundColor: '#EEF2FF', paddingHorizontal: 9, paddingVertical: 4, borderRadius: 12 },
  suggChipText: { fontSize: 11.5, color: '#4338CA', fontWeight: '600' },
  reviewRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  acceptBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#16A34A', paddingHorizontal: 14, paddingVertical: 7, borderRadius: 8 },
  acceptText: { color: '#FFF', fontWeight: '700', fontSize: 12.5 },
  dismissBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F1F5F9', paddingHorizontal: 14, paddingVertical: 7, borderRadius: 8 },
  dismissText: { color: '#64748B', fontWeight: '700', fontSize: 12.5 },
  rateRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  rateLabel: { fontSize: 12, color: '#92400E', fontWeight: '600', marginRight: 4 },
});
