/**
 * Knowledge Marketplace (Collaboration Epic Phase D + E buy flow).
 * Browse published decisions, view their structure, free-clone or paid-clone
 * (Razorpay), and publish your own decisions (view-only / free / paid tiers).
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, FlatList, RefreshControl, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

const TIER_META: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  view_only: { label: 'View only', color: '#64748B', bg: '#F1F5F9', icon: 'eye-outline' },
  free_clone: { label: 'Free clone', color: '#16A34A', bg: '#DCFCE7', icon: 'gift-outline' },
  paid_clone: { label: 'Paid clone', color: '#9333EA', bg: '#F3E8FF', icon: 'card-outline' },
};

async function loadRazorpayScript() {
  const w = window as any;
  if (w.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('failed to load Razorpay'));
    document.body.appendChild(script);
  });
}

export default function MarketplaceScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<'browse' | 'mine'>('browse');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('');

  const [active, setActive] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [myStars, setMyStars] = useState(0);

  const rateListing = async (stars: number) => {
    setMyStars(stars);
    try {
      const r = await api.post(`/karma/rate/marketplace/${active.listing_id}`, { stars });
      showAlert('Thanks for rating!', r.data.karma_awarded ? `Awarded ${r.data.karma_awarded} karma to the author.` : 'Your rating was saved.');
    } catch (e: any) {
      showAlert('Rate', e?.response?.data?.detail || 'Clone this decision first to rate it.');
      setMyStars(0);
    }
  };

  // publish flow
  const [showPublish, setShowPublish] = useState(false);
  const [myDecisions, setMyDecisions] = useState<any[]>([]);
  const [pubDecision, setPubDecision] = useState<any>(null);
  const [pubTier, setPubTier] = useState('free_clone');
  const [pubPriceInr, setPubPriceInr] = useState('');
  const [pubKarma, setPubKarma] = useState('');
  const [pubDesc, setPubDesc] = useState('');
  const [pubTags, setPubTags] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'mine') {
        const r = await api.get('/marketplace/mine');
        setItems(r.data?.items || []);
      } else {
        const qs = new URLSearchParams();
        if (search.trim()) qs.set('search', search.trim());
        if (tierFilter) qs.set('tier', tierFilter);
        const r = await api.get(`/marketplace${qs.toString() ? `?${qs.toString()}` : ''}`);
        setItems(r.data?.items || []);
      }
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, [tab, search, tierFilter]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (listing: any) => {
    setActive(listing); setDetail(null); setDetailLoading(true);
    try { const r = await api.get(`/marketplace/${listing.listing_id}`); setDetail(r.data); }
    catch { showAlert('Error', 'Could not load listing'); }
    finally { setDetailLoading(false); }
  };
  const closeDetail = () => { setActive(null); setDetail(null); };

  const freeClone = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/marketplace/${active.listing_id}/clone`);
      showAlert('Cloned ✅', 'Added to your decisions. Open it from your Dezider list to start scoring.', [
        { text: 'OK', onPress: () => { closeDetail(); } },
      ]);
      load();
      return r.data;
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Clone failed');
    } finally { setBusy(false); }
  };

  const buyClone = async () => {
    setBusy(true);
    try {
      const orderRes = await api.post(`/marketplace/${active.listing_id}/create-order`);
      const data = orderRes.data;
      if (data.already_purchased) {
        showAlert('Already purchased', 'You already own this. Cloning now…');
        await api.post(`/marketplace/${active.listing_id}/clone`);
        closeDetail(); load(); return;
      }
      if (Platform.OS === 'web') {
        await loadRazorpayScript();
        const rzp = new (window as any).Razorpay({
          key: data.key_id, amount: data.amount, currency: data.currency,
          name: 'Dezider Marketplace', description: active.title, order_id: data.order_id,
          prefill: { name: data.user_name, email: data.user_email },
          theme: { color: '#9333EA' },
          handler: async (resp: any) => {
            try {
              const v = await api.post(`/marketplace/${active.listing_id}/verify-payment`, resp);
              void v;
              showAlert('Purchase successful 🎉', 'The decision was cloned to your Dezider list.');
              closeDetail(); load();
            } catch (err: any) {
              showAlert('Verification failed', err?.response?.data?.detail || 'Contact support.');
            }
          },
          modal: { ondismiss: () => setBusy(false) },
        });
        rzp.open();
      } else {
        Linking.openURL(`https://checkout.razorpay.com/v1/checkout/embedded?key_id=${data.key_id}&order_id=${data.order_id}`);
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not start checkout.');
    } finally { setTimeout(() => setBusy(false), 1000); }
  };

  const unpublish = async () => {
    setBusy(true);
    try { await api.post(`/marketplace/${active.listing_id}/unpublish`); closeDetail(); load(); }
    catch { showAlert('Error', 'Failed'); }
    finally { setBusy(false); }
  };

  // ---- publish ----
  const openPublish = async () => {
    setShowPublish(true);
    try {
      const r = await api.get('/decisions');
      const list = (r.data?.items || r.data || []).filter((d: any) => (d.factors?.length || 0) > 0 && (d.options?.length || 0) > 0);
      setMyDecisions(list);
    } catch { setMyDecisions([]); }
  };
  const doPublish = async () => {
    if (!pubDecision) { showAlert('Pick a decision', 'Select a decision to publish.'); return; }
    if (pubTier === 'paid_clone' && !pubPriceInr && !pubKarma) { showAlert('Set price', 'Enter an INR price and/or karma price for paid clone.'); return; }
    setBusy(true);
    try {
      await api.post('/marketplace/publish', {
        decision_id: pubDecision.id,
        tier: pubTier,
        price_inr: pubPriceInr ? parseInt(pubPriceInr, 10) : null,
        price_karma: pubKarma ? parseInt(pubKarma, 10) : null,
        description: pubDesc,
        tags: pubTags.split(',').map(t => t.trim()).filter(Boolean),
      });
      setShowPublish(false); setPubDecision(null); setPubPriceInr(''); setPubKarma(''); setPubDesc(''); setPubTags('');
      setTab('mine'); showAlert('Published 🛍️', 'Your decision is now on the marketplace.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Publish failed'); }
    finally { setBusy(false); }
  };

  const renderCard = ({ item }: { item: any }) => {
    const tm = TIER_META[item.tier] || TIER_META.view_only;
    return (
      <TouchableOpacity style={styles.card} onPress={() => openDetail(item)} activeOpacity={0.85}>
        <View style={styles.cardTop}>
          <View style={[styles.tierBadge, { backgroundColor: tm.bg }]}>
            <Ionicons name={tm.icon} size={12} color={tm.color} />
            <Text style={[styles.tierText, { color: tm.color }]}>{tm.label}</Text>
          </View>
          {item.tier === 'paid_clone' && (item.price_inr > 0) && <Text style={styles.price}>₹{item.price_inr}</Text>}
          {item.status === 'unpublished' && <View style={styles.unpubBadge}><Text style={styles.unpubText}>Unpublished</Text></View>}
        </View>
        <Text style={styles.cardTitle} numberOfLines={2}>{item.title}</Text>
        {!!item.description && <Text style={styles.cardDesc} numberOfLines={2}>{item.description}</Text>}
        <View style={styles.cardMeta}>
          <Text style={styles.metaText}>by {item.owner_name}</Text>
          <Text style={styles.metaDot}>·</Text>
          <Text style={styles.metaText}>{item.snapshot?.factor_count ?? 0} factors · {item.snapshot?.option_count ?? 0} options</Text>
        </View>
        <View style={styles.cardStats}>
          <Text style={styles.stat}><Ionicons name="copy-outline" size={12} color="#64748B" /> {item.clone_count || 0}</Text>
          <Text style={styles.stat}><Ionicons name="eye-outline" size={12} color="#64748B" /> {item.view_count || 0}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  const tm = active ? (TIER_META[active.tier] || TIER_META.view_only) : null;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#9333EA', '#6B21A8']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Marketplace</Text>
        <TouchableOpacity style={styles.iconHdr} onPress={openPublish} testID="open-publish">
          <Ionicons name="add-circle-outline" size={24} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      <View style={styles.tabRow}>
        {(['browse', 'mine'] as const).map(t => (
          <TouchableOpacity key={t} style={[styles.tab, tab === t && styles.tabActive]} onPress={() => setTab(t)}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t === 'browse' ? 'Browse' : 'My Listings'}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {tab === 'browse' && (
        <>
          <View style={styles.searchRow}>
            <Ionicons name="search" size={16} color="#94A3B8" />
            <TextInput style={styles.searchInput} placeholder="Search decisions…" value={search} onChangeText={setSearch} returnKeyType="search" onSubmitEditing={load} />
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow} contentContainerStyle={{ gap: 8, paddingHorizontal: 12 }}>
            {['', 'free_clone', 'paid_clone', 'view_only'].map(t => (
              <TouchableOpacity key={t || 'all'} style={[styles.filterChip, tierFilter === t && styles.filterChipActive]} onPress={() => setTierFilter(t)}>
                <Text style={[styles.filterChipText, tierFilter === t && styles.filterChipTextActive]}>{t ? TIER_META[t].label : 'All'}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </>
      )}

      {loading ? (
        <ActivityIndicator style={{ marginTop: 40 }} color="#9333EA" />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.listing_id}
          contentContainerStyle={{ padding: 14, paddingBottom: 60 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="storefront-outline" size={46} color="#E9D5FF" />
              <Text style={styles.emptyTitle}>{tab === 'mine' ? 'No listings yet' : 'Nothing here yet'}</Text>
              <Text style={styles.emptyDesc}>{tab === 'mine'
                ? 'Publish a completed decision to share your reasoning — free or paid.'
                : 'No published decisions match. Check back soon or publish your own.'}</Text>
              {tab === 'mine' && (
                <TouchableOpacity style={styles.emptyBtn} onPress={openPublish}>
                  <Ionicons name="add" size={18} color="#FFF" /><Text style={styles.emptyBtnText}>Publish a decision</Text>
                </TouchableOpacity>
              )}
            </View>
          }
          renderItem={renderCard}
        />
      )}

      {/* ---- Detail modal ---- */}
      <Modal visible={!!active} transparent animationType="slide" onRequestClose={closeDetail}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle} numberOfLines={1}>{active?.title}</Text>
              <TouchableOpacity onPress={closeDetail}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            {detailLoading || !detail ? (
              <ActivityIndicator style={{ marginVertical: 40 }} color="#9333EA" />
            ) : (
              <ScrollView style={{ maxHeight: '90%' }} showsVerticalScrollIndicator={false}>
                <View style={styles.detailRow}>
                  {tm && <View style={[styles.tierBadge, { backgroundColor: tm.bg }]}>
                    <Ionicons name={tm.icon} size={12} color={tm.color} /><Text style={[styles.tierText, { color: tm.color }]}>{tm.label}</Text>
                  </View>}
                  {detail.tier === 'paid_clone' && detail.price_inr > 0 && <Text style={styles.detailPrice}>₹{detail.price_inr}</Text>}
                  {detail.tier === 'paid_clone' && detail.price_karma > 0 && <Text style={styles.karmaPrice}>or {detail.price_karma} ⭐</Text>}
                </View>
                <Text style={styles.detailOwner}>Shared by {detail.owner_name}</Text>
                {!!detail.description && <Text style={styles.detailDesc}>{detail.description}</Text>}

                <View style={styles.snapBox}>
                  <Text style={styles.snapTitle}>{`What's inside ${detail.snapshot?.locked ? '(preview — unlock by purchasing)' : ''}`}</Text>
                  <Text style={styles.snapLine}>🏷 {detail.snapshot?.factor_count ?? 0} factors{detail.snapshot?.factor_names?.length ? `: ${detail.snapshot.factor_names.join(', ')}${detail.snapshot?.locked ? '…' : ''}` : ''}</Text>
                  <Text style={styles.snapLine}>🔘 {detail.snapshot?.option_count ?? 0} options{detail.snapshot?.option_names?.length ? `: ${detail.snapshot.option_names.join(', ')}` : ''}</Text>
                </View>

                {!!detail.tags?.length && (
                  <View style={styles.chips}>
                    {detail.tags.map((t: string) => <View key={t} style={styles.tagChip}><Text style={styles.tagChipText}>#{t}</Text></View>)}
                  </View>
                )}

                {detail.is_owner ? (
                  <View style={styles.ownerStats}>
                    <Text style={styles.ownerStatText}>📋 {detail.clone_count} clones · 👁 {detail.view_count} views</Text>
                    <TouchableOpacity style={styles.unpubBtn} onPress={unpublish} disabled={busy}>
                      <Text style={styles.unpubBtnText}>{detail.status === 'active' ? 'Unpublish' : 'Unpublished'}</Text>
                    </TouchableOpacity>
                  </View>
                ) : detail.tier === 'view_only' ? (
                  <View style={styles.viewOnlyNote}><Ionicons name="eye-outline" size={16} color="#64748B" /><Text style={styles.viewOnlyText}>This decision is view-only and cannot be cloned.</Text></View>
                ) : detail.tier === 'free_clone' ? (
                  <TouchableOpacity style={styles.cloneBtn} onPress={freeClone} disabled={busy}>
                    {busy ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="copy" size={18} color="#FFF" /><Text style={styles.cloneBtnText}>Clone for free</Text></>}
                  </TouchableOpacity>
                ) : detail.purchased ? (
                  <TouchableOpacity style={styles.cloneBtn} onPress={freeClone} disabled={busy}>
                    {busy ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="copy" size={18} color="#FFF" /><Text style={styles.cloneBtnText}>Clone (already purchased)</Text></>}
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={[styles.cloneBtn, { backgroundColor: '#9333EA' }]} onPress={buyClone} disabled={busy}>
                    {busy ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="card" size={18} color="#FFF" /><Text style={styles.cloneBtnText}>Buy &amp; clone · ₹{detail.price_inr}</Text></>}
                  </TouchableOpacity>
                )}
                {/* rate (non-owner) */}
                {!detail.is_owner && (
                  <View style={styles.rateBox}>
                    <Text style={styles.rateTitle}>Rate this decision{detail.rating_avg != null ? `  ·  ${detail.rating_avg}★ (${detail.rating_count})` : ''}</Text>
                    <View style={styles.rateStars}>
                      {[1, 2, 3, 4, 5].map(s => (
                        <TouchableOpacity key={s} onPress={() => rateListing(s)}>
                          <Ionicons name={myStars >= s ? 'star' : 'star-outline'} size={28} color="#F59E0B" />
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                )}
                <View style={{ height: 24 }} />
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>

      {/* ---- Publish modal ---- */}
      <Modal visible={showPublish} transparent animationType="slide" onRequestClose={() => setShowPublish(false)}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Publish a decision</Text>
              <TouchableOpacity onPress={() => setShowPublish(false)}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: '88%' }} showsVerticalScrollIndicator={false}>
              <Text style={styles.fieldLabel}>Select decision (must have factors &amp; options)</Text>
              {myDecisions.length === 0 ? (
                <Text style={styles.noDecisions}>No eligible decisions found. Complete a decision&apos;s factors and options first.</Text>
              ) : myDecisions.map(d => (
                <TouchableOpacity key={d.id} style={[styles.decRow, pubDecision?.id === d.id && styles.decRowActive]} onPress={() => setPubDecision(d)}>
                  <Ionicons name={pubDecision?.id === d.id ? 'radio-button-on' : 'radio-button-off'} size={18} color="#9333EA" />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.decTitle} numberOfLines={1}>{d.title}</Text>
                    <Text style={styles.decMeta}>{d.factors?.length || 0} factors · {d.options?.length || 0} options</Text>
                  </View>
                </TouchableOpacity>
              ))}

              <Text style={styles.fieldLabel}>Access tier</Text>
              <View style={styles.tierPick}>
                {(['view_only', 'free_clone', 'paid_clone'] as const).map(t => {
                  const m = TIER_META[t];
                  return (
                    <TouchableOpacity key={t} style={[styles.tierOpt, pubTier === t && { borderColor: m.color, backgroundColor: m.bg }]} onPress={() => setPubTier(t)}>
                      <Ionicons name={m.icon} size={18} color={m.color} />
                      <Text style={[styles.tierOptText, pubTier === t && { color: m.color }]}>{m.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {pubTier === 'paid_clone' && (
                <>
                  <Text style={styles.fieldLabel}>Price (₹ INR)</Text>
                  <TextInput style={styles.input} value={pubPriceInr} onChangeText={(t) => setPubPriceInr(t.replace(/[^0-9]/g, ''))} placeholder="e.g. 99" keyboardType="numeric" />
                  <Text style={styles.fieldLabel}>Or price in Karma points (optional)</Text>
                  <TextInput style={styles.input} value={pubKarma} onChangeText={(t) => setPubKarma(t.replace(/[^0-9]/g, ''))} placeholder="e.g. 50" keyboardType="numeric" />
                </>
              )}

              <Text style={styles.fieldLabel}>Description</Text>
              <TextInput style={[styles.input, { minHeight: 70, textAlignVertical: 'top' }]} value={pubDesc} onChangeText={setPubDesc} placeholder="What's this decision about & who benefits?" multiline />
              <Text style={styles.fieldLabel}>Tags (comma-separated)</Text>
              <TextInput style={styles.input} value={pubTags} onChangeText={setPubTags} placeholder="career, relocation, finance" />

              <TouchableOpacity style={styles.publishBtn} onPress={doPublish} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.publishBtnText}>Publish to Marketplace</Text>}
              </TouchableOpacity>
              <View style={{ height: 20 }} />
            </ScrollView>
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
  tabActive: { backgroundColor: '#9333EA' },
  tabText: { fontSize: 13, fontWeight: '700', color: '#475569' },
  tabTextActive: { color: '#FFF' },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, margin: 12, marginBottom: 8, paddingHorizontal: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  filterRow: { maxHeight: 42, marginBottom: 4 },
  filterChip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0' },
  filterChipActive: { backgroundColor: '#9333EA', borderColor: '#9333EA' },
  filterChipText: { fontSize: 12.5, fontWeight: '600', color: '#475569' },
  filterChipTextActive: { color: '#FFF' },
  empty: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: '#0F172A' },
  emptyDesc: { fontSize: 13, color: '#64748B', textAlign: 'center', paddingHorizontal: 28, lineHeight: 18 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#9333EA', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, marginTop: 10 },
  emptyBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#EEF2F7' },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  tierBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  tierText: { fontSize: 10.5, fontWeight: '800' },
  price: { fontSize: 14, fontWeight: '800', color: '#9333EA' },
  unpubBadge: { backgroundColor: '#FEE2E2', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  unpubText: { fontSize: 10, fontWeight: '700', color: '#B91C1C' },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  cardDesc: { fontSize: 13, color: '#475569', marginTop: 3, lineHeight: 18 },
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8, flexWrap: 'wrap' },
  metaText: { fontSize: 11.5, color: '#64748B' },
  metaDot: { color: '#CBD5E1' },
  cardStats: { flexDirection: 'row', gap: 14, marginTop: 8, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 8 },
  stat: { fontSize: 12, color: '#64748B', fontWeight: '600' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '92%' },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A', flex: 1, marginRight: 8 },
  detailRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  detailPrice: { fontSize: 18, fontWeight: '800', color: '#9333EA' },
  karmaPrice: { fontSize: 13, fontWeight: '700', color: '#F59E0B' },
  detailOwner: { fontSize: 12.5, color: '#64748B', marginBottom: 8 },
  detailDesc: { fontSize: 13.5, color: '#334155', lineHeight: 20, marginBottom: 12 },
  snapBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  snapTitle: { fontSize: 12, fontWeight: '800', color: '#475569', marginBottom: 5 },
  snapLine: { fontSize: 12.5, color: '#334155', marginTop: 3, lineHeight: 18 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  tagChip: { backgroundColor: '#F3E8FF', paddingHorizontal: 9, paddingVertical: 4, borderRadius: 12 },
  tagChipText: { fontSize: 11.5, color: '#9333EA', fontWeight: '600' },
  ownerStats: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ownerStatText: { fontSize: 13, fontWeight: '600', color: '#334155' },
  unpubBtn: { backgroundColor: '#FEE2E2', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  unpubBtnText: { fontSize: 12.5, fontWeight: '700', color: '#B91C1C' },
  viewOnlyNote: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 10, padding: 12 },
  viewOnlyText: { fontSize: 13, color: '#64748B', flex: 1 },
  cloneBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#16A34A', paddingVertical: 14, borderRadius: 12 },
  cloneBtnText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 6, marginTop: 12 },
  noDecisions: { fontSize: 13, color: '#94A3B8', paddingVertical: 10 },
  decRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 6 },
  decRowActive: { borderColor: '#9333EA', backgroundColor: '#FAF5FF' },
  decTitle: { fontSize: 14, fontWeight: '600', color: '#0F172A' },
  decMeta: { fontSize: 11.5, color: '#64748B' },
  tierPick: { flexDirection: 'row', gap: 8 },
  tierOpt: { flex: 1, alignItems: 'center', gap: 4, paddingVertical: 12, borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E8F0' },
  tierOptText: { fontSize: 11.5, fontWeight: '700', color: '#475569' },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA' },
  publishBtn: { backgroundColor: '#9333EA', paddingVertical: 14, borderRadius: 12, alignItems: 'center', marginTop: 18 },
  publishBtnText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
  rateBox: { backgroundColor: '#FFFBEB', borderRadius: 12, padding: 14, marginTop: 14, borderWidth: 1, borderColor: '#FDE68A' },
  rateTitle: { fontSize: 13, fontWeight: '700', color: '#92400E', marginBottom: 8 },
  rateStars: { flexDirection: 'row', gap: 8 },
});
