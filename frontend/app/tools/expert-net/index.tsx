/**
 * /tools/expert-net  — ExpertNet hub
 *
 * 5 tabs:
 *   • Discover    — search/filter experts, connect-now or book
 *   • Bookings    — my bookings (user role) + start-call when confirmed
 *   • Recommendations — solutions experts recommended → linked CTT tasks + delivery tracking
 *   • Webinars    — discover/register/join 1:many sessions
 *   • Be an Expert — onboarding / profile / availability / intake form / my-incoming-bookings
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, KeyboardAvoidingView, Platform, Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';

type Tab = 'discover' | 'bookings' | 'recommendations' | 'webinars' | 'manage';

interface Expert {
  expert_id: string;
  user_id?: string;
  name: string;
  headline?: string;
  bio?: string;
  specializations?: string[];
  languages?: string[];
  hourly_rate_inr?: number;
  rating_avg?: number;
  rating_count?: number;
  is_online?: boolean;
  accepts_instant_calls?: boolean;
  photo_url?: string;
}

const DEFAULT_LANGS = ['en', 'hi', 'ta', 'te', 'kn', 'ml', 'mr', 'bn', 'gu'];

export default function ExpertNetScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('discover');

  // shared
  const [me, setMe] = useState<any>(null);
  useEffect(() => { (async () => { try { const r = await api.get('/auth/me'); setMe(r.data); } catch { /* */ } })(); }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>ExpertNet</Text>
        <View style={{ width: 22 }} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabsRow} contentContainerStyle={{ paddingHorizontal: 12, gap: 6 }}>
        {(['discover', 'bookings', 'recommendations', 'webinars', 'manage'] as Tab[]).map(t => (
          <TouchableOpacity key={t} testID={`xn-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === 'manage' ? 'Be an Expert' : t.charAt(0).toUpperCase() + t.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'discover' && <DiscoverTab onPickExpert={() => null} />}
      {tab === 'bookings' && <BookingsTab />}
      {tab === 'recommendations' && <RecommendationsTab />}
      {tab === 'webinars' && <WebinarsTab />}
      {tab === 'manage' && <ManageTab />}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Discover tab
// ---------------------------------------------------------------------------
function DiscoverTab({ onPickExpert }: { onPickExpert: (e: Expert) => void }) {
  const router = useRouter();
  const [items, setItems] = useState<Expert[]>([]);
  const [loading, setLoading] = useState(true);
  const [language, setLanguage] = useState<string | null>(null);
  const [onlyInstant, setOnlyInstant] = useState(false);
  const [maxRate, setMaxRate] = useState<number | null>(null);
  const [minRating, setMinRating] = useState<number | null>(null);
  const [sort, setSort] = useState<string>('rating');
  const [q, setQ] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (language) params.language = language;
      if (onlyInstant) params.only_instant = true;
      if (maxRate) params.max_rate = maxRate;
      if (minRating) params.min_rating = minRating;
      if (sort) params.sort = sort;
      if (q.trim()) params.specialization = q.trim();
      const res = await api.get('/expert-net/experts', { params });
      setItems(res.data?.items || []);
    } catch (e: any) {
      showAlert('Discover error', e?.response?.data?.detail || e.message);
    } finally { setLoading(false); }
  }, [language, onlyInstant, maxRate, minRating, sort, q]);

  useEffect(() => { load(); }, [load]);

  const connectNow = async (e: Expert) => {
    try {
      const res = await api.post(`/expert-net/experts/${e.expert_id}/connect-now`, {});
      router.push(res.data.video_url as any);
    } catch (err: any) {
      showAlert('Cannot connect', err?.response?.data?.detail || err.message);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <View style={styles.searchBar}>
        <Ionicons name="search" size={16} color={COLORS.textMuted} />
        <TextInput placeholder="Search by specialization (mental_health, tax, ...)" placeholderTextColor={COLORS.textMuted} style={{ flex: 1, color: COLORS.textPrimary, fontSize: 13 }} value={q} onChangeText={setQ} onSubmitEditing={load} />
      </View>

      {/* Filters */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, marginBottom: 8 }}>
        <TouchableOpacity onPress={() => setOnlyInstant(!onlyInstant)} style={[styles.filterChip, onlyInstant && styles.filterChipActive]}>
          <Text style={[styles.filterChipText, onlyInstant && styles.filterChipTextActive]}>⚡ Instant only</Text>
        </TouchableOpacity>
        {[null, 1000, 2500, 5000].map(r => (
          <TouchableOpacity key={String(r)} onPress={() => setMaxRate(r)} style={[styles.filterChip, maxRate === r && styles.filterChipActive]}>
            <Text style={[styles.filterChipText, maxRate === r && styles.filterChipTextActive]}>{r ? `≤ ₹${r}/hr` : 'Any rate'}</Text>
          </TouchableOpacity>
        ))}
        {DEFAULT_LANGS.map(lng => (
          <TouchableOpacity key={lng} onPress={() => setLanguage(language === lng ? null : lng)} style={[styles.filterChip, language === lng && styles.filterChipActive]}>
            <Text style={[styles.filterChipText, language === lng && styles.filterChipTextActive]}>{lng}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12 }}>
        {(['rating', 'rate_asc', 'rate_desc', 'newest'] as const).map(s => (
          <TouchableOpacity key={s} onPress={() => setSort(s)} style={[styles.sortChip, sort === s && styles.sortChipActive]}>
            <Text style={[styles.sortChipText, sort === s && styles.sortChipTextActive]}>{s.replace('_', ' ')}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? <ActivityIndicator color={COLORS.primary} /> :
       items.length === 0 ? (
        <View style={styles.empty}><Ionicons name="people-outline" size={32} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No experts match your filters</Text>
        </View>
      ) : items.map(e => (
        <View key={e.expert_id} style={styles.expertCard}>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={[styles.avatarLg, { backgroundColor: '#7C3AED' }]}>
              <Text style={{ color: '#FFF', fontSize: 18, fontWeight: '700' }}>{(e.name || 'E')[0]}</Text>
              {e.is_online && <View style={styles.onlineDot} />}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.expertName} numberOfLines={1}>{e.name}</Text>
              {e.headline && <Text style={styles.expertHeadline} numberOfLines={1}>{e.headline}</Text>}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                {e.hourly_rate_inr ? <Text style={styles.metaPill}>₹{e.hourly_rate_inr}/hr</Text> : <Text style={styles.metaPill}>Free intro</Text>}
                {e.rating_avg ? <Text style={styles.metaPill}>★ {e.rating_avg.toFixed(1)} ({e.rating_count})</Text> : null}
                {(e.languages || []).slice(0, 3).map(lng => <Text key={lng} style={styles.metaPill}>{lng}</Text>)}
              </View>
            </View>
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
            <TouchableOpacity testID={`xn-detail-${e.expert_id}`} style={[styles.btnSecondary, { flex: 1 }]} onPress={() => router.push(`/tools/expert-net/${e.expert_id}` as any)}>
              <Text style={styles.btnSecondaryText}>View profile</Text>
            </TouchableOpacity>
            {e.is_online && e.accepts_instant_calls ? (
              <TouchableOpacity testID={`xn-connect-${e.expert_id}`} style={[styles.btnPrimary, { flex: 1, backgroundColor: '#10B981' }]} onPress={() => connectNow(e)}>
                <Ionicons name="call" size={14} color="#FFF" />
                <Text style={styles.btnPrimaryText}>Connect now</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity testID={`xn-book-${e.expert_id}`} style={[styles.btnPrimary, { flex: 1 }]} onPress={() => router.push(`/tools/expert-net/${e.expert_id}` as any)}>
                <Ionicons name="calendar" size={14} color="#FFF" />
                <Text style={styles.btnPrimaryText}>Book slot</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Bookings tab
// ---------------------------------------------------------------------------
function BookingsTab() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { (async () => {
    try { const r = await api.get('/expert-net/bookings?role=user'); setItems(r.data?.items || []); }
    catch (e: any) { showAlert('Bookings', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  })(); }, []);

  const startCall = async (b: any) => {
    try { const r = await api.post(`/expert-net/bookings/${b.booking_id}/start-call`, {}); router.push(r.data.video_url as any); }
    catch (e: any) { showAlert('Cannot start', e?.response?.data?.detail || e.message); }
  };

  const cancel = async (b: any) => {
    try { await api.post(`/expert-net/bookings/${b.booking_id}/cancel`, {}); showAlert('Cancelled', 'Booking cancelled'); }
    catch (e: any) { showAlert('Cancel failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      {loading ? <ActivityIndicator color={COLORS.primary} /> : items.length === 0 ? (
        <View style={styles.empty}><Ionicons name="calendar-outline" size={32} color={COLORS.textMuted} /><Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No bookings yet</Text></View>
      ) : items.map(b => (
        <View key={b.booking_id} style={styles.bookingCard}>
          <Text style={styles.expertName}>{b.expert_name}</Text>
          <Text style={styles.metaPill}>{new Date(b.slot_start).toLocaleString()} · {b.duration_minutes}m</Text>
          <Text style={[styles.statusPill, {
            backgroundColor: b.status === 'confirmed' ? '#10B98122' : b.status === 'pending' ? '#F59E0B22' : b.status === 'in_progress' ? '#3B82F622' : '#EF444422',
            color: b.status === 'confirmed' ? '#059669' : b.status === 'pending' ? '#D97706' : b.status === 'in_progress' ? '#2563EB' : '#DC2626',
          }]}>{b.status}</Text>
          {!!b.note && <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 4 }}>{b.note}</Text>}
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
            {(b.status === 'confirmed' || b.status === 'in_progress') && (
              <TouchableOpacity style={[styles.btnPrimary, { flex: 1 }]} onPress={() => startCall(b)}>
                <Ionicons name="videocam" size={14} color="#FFF" /><Text style={styles.btnPrimaryText}>Join call</Text>
              </TouchableOpacity>
            )}
            {b.status !== 'cancelled' && b.status !== 'completed' && (
              <TouchableOpacity style={[styles.btnSecondary, { flex: 1 }]} onPress={() => cancel(b)}>
                <Text style={styles.btnSecondaryText}>Cancel</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Recommendations + Deliveries tab (combined)
// ---------------------------------------------------------------------------
function RecommendationsTab() {
  const [recs, setRecs] = useState<any[]>([]);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { (async () => {
    try {
      const [r1, r2] = await Promise.all([api.get('/expert-net/recommendations'), api.get('/expert-net/deliveries')]);
      setRecs(r1.data?.items || []);
      setDeliveries(r2.data?.items || []);
    } catch (e: any) { showAlert('Load error', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  })(); }, []);

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      {loading ? <ActivityIndicator color={COLORS.primary} /> : (
        <>
          <Text style={styles.sectionH}>Expert recommendations</Text>
          {recs.length === 0 ? <View style={styles.empty}><Text style={{ color: COLORS.textMuted }}>None yet</Text></View> :
            recs.map(r => (
              <View key={r.recommendation_id} style={styles.recCard}>
                <Text style={styles.expertName}>{r.solution_name}</Text>
                <Text style={styles.metaSmall}>by {r.expert_name} · {new Date(r.created_at).toLocaleDateString()}</Text>
                {!!r.note && <Text style={{ fontSize: 13, color: COLORS.textSecondary, marginTop: 4 }}>{r.note}</Text>}
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  {r.linked_ctt_task_id && <Text style={[styles.tagPill, { backgroundColor: '#3B82F622', color: '#1E40AF' }]}>📋 CTT task created</Text>}
                  {r.linked_routine_id && <Text style={[styles.tagPill, { backgroundColor: '#10B98122', color: '#059669' }]}>🔁 Routine created</Text>}
                </View>
              </View>
            ))}

          <Text style={[styles.sectionH, { marginTop: 16 }]}>Delivery tracking</Text>
          {deliveries.length === 0 ? <View style={styles.empty}><Text style={{ color: COLORS.textMuted }}>None yet</Text></View> :
            deliveries.map(d => (
              <View key={d.order_id} style={styles.recCard}>
                <Text style={styles.expertName}>{d.solution_name}</Text>
                <Text style={styles.metaSmall}>order {d.order_id}</Text>
                <DeliveryProgress status={d.status} />
                {!!d.tracking_number && (
                  <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 4 }}>
                    Tracking: {d.tracking_number}{d.tracking_url ? ` · ${d.tracking_url}` : ''}
                  </Text>
                )}
              </View>
            ))}
        </>
      )}
    </ScrollView>
  );
}

const DELIVERY_STAGES = ['ordered', 'confirmed', 'shipped', 'in_transit', 'out_for_delivery', 'delivered'];

function DeliveryProgress({ status }: { status: string }) {
  const idx = DELIVERY_STAGES.indexOf(status);
  return (
    <View style={{ marginTop: 8 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        {DELIVERY_STAGES.map((s, i) => (
          <React.Fragment key={s}>
            <View style={{
              width: 16, height: 16, borderRadius: 8,
              backgroundColor: i <= idx ? COLORS.primary : '#E5E7EB',
              alignItems: 'center', justifyContent: 'center',
            }}>
              {i <= idx && <Ionicons name="checkmark" size={10} color="#FFF" />}
            </View>
            {i < DELIVERY_STAGES.length - 1 && (
              <View style={{ flex: 1, height: 2, backgroundColor: i < idx ? COLORS.primary : '#E5E7EB' }} />
            )}
          </React.Fragment>
        ))}
      </View>
      <Text style={{ fontSize: 11, color: COLORS.textSecondary, marginTop: 4, textTransform: 'capitalize' }}>
        {status === 'cancelled' ? '❌ cancelled' : status === 'delayed' ? '⚠️ delayed' : status.replace(/_/g, ' ')}
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Webinars tab
// ---------------------------------------------------------------------------
function WebinarsTab() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [freeOnly, setFreeOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { upcoming_only: true };
      if (freeOnly) params.free_only = true;
      const r = await api.get('/expert-net/webinars', { params });
      setItems(r.data?.items || []);
    } catch (e: any) { showAlert('Webinars', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [freeOnly]);
  useEffect(() => { load(); }, [load]);

  const register = async (w: any) => {
    try { const r = await api.post('/expert-net/webinars/register', { webinar_id: w.webinar_id });
      showAlert('Registered', r.data?.payment_status === 'paid_free' ? 'You are in!' : 'Payment pending — open Time Store.');
      load();
    } catch (e: any) { showAlert('Register failed', e?.response?.data?.detail || e.message); }
  };

  const join = async (w: any) => {
    try { const r = await api.post(`/expert-net/webinars/${w.webinar_id}/start`, {}); router.push(r.data.video_url as any); }
    catch (e: any) {
      // Non-host attempting → for now we open the video session if it exists
      if (w.video_session_id) router.push(`/tools/jitsi-room?room=${w.video_session_id}&subject=Webinar` as any);
      else showAlert('Webinar', e?.response?.data?.detail || 'Webinar not started yet — please wait for the host.');
    }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Switch value={freeOnly} onValueChange={setFreeOnly} />
        <Text style={{ color: COLORS.textPrimary, fontSize: 12 }}>Free only</Text>
      </View>
      {loading ? <ActivityIndicator color={COLORS.primary} /> : items.length === 0 ? (
        <View style={styles.empty}><Ionicons name="megaphone-outline" size={32} color={COLORS.textMuted} /><Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No upcoming webinars</Text></View>
      ) : items.map(w => (
        <View key={w.webinar_id} style={styles.webinarCard}>
          <Text style={styles.expertName}>{w.title}</Text>
          <Text style={styles.metaSmall}>{new Date(w.starts_at).toLocaleString()} · {w.duration_minutes} min</Text>
          {!!w.expert_name && <Text style={styles.metaSmall}>by {w.expert_name}</Text>}
          {!!w.description && <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 4 }} numberOfLines={3}>{w.description}</Text>}
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
            <Text style={[styles.tagPill, { backgroundColor: w.is_free ? '#10B98122' : '#F59E0B22', color: w.is_free ? '#059669' : '#D97706' }]}>
              {w.is_free ? 'Free' : `₹${w.price_inr}`}
            </Text>
            {w.capacity ? <Text style={styles.tagPill}>cap {w.registered_count}/{w.capacity}</Text> : null}
            {w.i_am_registered ? <Text style={[styles.tagPill, { backgroundColor: '#3B82F622', color: '#1E40AF' }]}>✓ Registered</Text> : null}
            {w.status === 'live' ? <Text style={[styles.tagPill, { backgroundColor: '#EF444422', color: '#DC2626' }]}>🔴 LIVE</Text> : null}
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
            {!w.i_am_registered && <TouchableOpacity style={[styles.btnPrimary, { flex: 1 }]} onPress={() => register(w)}><Text style={styles.btnPrimaryText}>Register</Text></TouchableOpacity>}
            {(w.i_am_registered || w.status === 'live') && <TouchableOpacity style={[styles.btnPrimary, { flex: 1, backgroundColor: '#10B981' }]} onPress={() => join(w)}><Ionicons name="videocam" size={14} color="#FFF" /><Text style={styles.btnPrimaryText}>Join</Text></TouchableOpacity>}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Manage tab — Be an Expert
// ---------------------------------------------------------------------------
function ManageTab() {
  const [profiles, setProfiles] = useState<Expert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState({ name: '', headline: '', specializations: '', languages: 'en,hi', hourly_rate_inr: '', accepts_instant_calls: false });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/auth/me');
      const all = await api.get('/expert-net/experts?sort=newest');
      setProfiles((all.data?.items || []).filter((e: Expert) => e.user_id === r.data?.user_id));
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!draft.name.trim()) return showAlert('Required', 'Name is required');
    try { setBusy(true);
      await api.post('/expert-net/experts', {
        name: draft.name,
        headline: draft.headline || undefined,
        specializations: draft.specializations.split(',').map(s => s.trim()).filter(Boolean),
        languages: draft.languages.split(',').map(s => s.trim()).filter(Boolean),
        hourly_rate_inr: draft.hourly_rate_inr ? parseInt(draft.hourly_rate_inr, 10) : undefined,
        accepts_instant_calls: draft.accepts_instant_calls,
      });
      showAlert('Created', 'Expert profile saved');
      setShowCreate(false);
      setDraft({ name: '', headline: '', specializations: '', languages: 'en,hi', hourly_rate_inr: '', accepts_instant_calls: false });
      load();
    } catch (e: any) { showAlert('Create failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const toggleOnline = async (e: Expert) => {
    try { await api.post(`/expert-net/experts/${e.expert_id}/online`, { is_online: !e.is_online }); load(); }
    catch (err: any) { showAlert('Toggle failed', err?.response?.data?.detail || err.message); }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <TouchableOpacity testID="xn-create-expert" style={[styles.btnPrimary, { marginBottom: 14 }]} onPress={() => setShowCreate(true)}>
        <Ionicons name="add" size={16} color="#FFF" />
        <Text style={styles.btnPrimaryText}>Create expert profile</Text>
      </TouchableOpacity>

      {loading ? <ActivityIndicator color={COLORS.primary} /> : profiles.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="briefcase-outline" size={32} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>You don't have an expert profile yet</Text>
        </View>
      ) : profiles.map(p => (
        <View key={p.expert_id} style={styles.expertCard}>
          <Text style={styles.expertName}>{p.name}</Text>
          {p.headline && <Text style={styles.expertHeadline}>{p.headline}</Text>}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <Text style={{ color: COLORS.textPrimary, fontSize: 12 }}>Online status</Text>
            <Switch value={!!p.is_online} onValueChange={() => toggleOnline(p)} />
            {p.accepts_instant_calls && <Text style={[styles.tagPill, { backgroundColor: '#10B98122', color: '#059669' }]}>⚡ Instant</Text>}
          </View>
        </View>
      ))}

      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.overlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Be an Expert</Text>
            <ScrollView>
              <Text style={styles.fieldLabel}>Display name *</Text>
              <TextInput style={styles.input} value={draft.name} onChangeText={v => setDraft({ ...draft, name: v })} placeholder="Dr. Priya Ramesh" placeholderTextColor={COLORS.textMuted} />
              <Text style={styles.fieldLabel}>Headline</Text>
              <TextInput style={styles.input} value={draft.headline} onChangeText={v => setDraft({ ...draft, headline: v })} placeholder="Clinical psychologist · 15 yrs" placeholderTextColor={COLORS.textMuted} />
              <Text style={styles.fieldLabel}>Specializations (comma-separated)</Text>
              <TextInput style={styles.input} value={draft.specializations} onChangeText={v => setDraft({ ...draft, specializations: v })} placeholder="mental_health, anxiety, parenting" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
              <Text style={styles.fieldLabel}>Languages (comma-separated)</Text>
              <TextInput style={styles.input} value={draft.languages} onChangeText={v => setDraft({ ...draft, languages: v })} placeholder="en, hi, ta" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
              <Text style={styles.fieldLabel}>Hourly rate (₹, optional)</Text>
              <TextInput style={styles.input} value={draft.hourly_rate_inr} onChangeText={v => setDraft({ ...draft, hourly_rate_inr: v })} keyboardType="numeric" />
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
                <Switch value={draft.accepts_instant_calls} onValueChange={v => setDraft({ ...draft, accepts_instant_calls: v })} />
                <Text style={{ color: COLORS.textPrimary, fontSize: 13 }}>Accept instant calls when online</Text>
              </View>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 16, marginBottom: 12 }}>
                <TouchableOpacity style={[styles.btnSecondary, { flex: 1 }]} onPress={() => setShowCreate(false)}><Text style={styles.btnSecondaryText}>Cancel</Text></TouchableOpacity>
                <TouchableOpacity style={[styles.btnPrimary, { flex: 1, opacity: busy ? 0.6 : 1 }]} disabled={busy} onPress={submit}>
                  {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Save</Text>}
                </TouchableOpacity>
              </View>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// styles
// ---------------------------------------------------------------------------
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  tabsRow: { backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider, maxHeight: 46 },
  tab: { paddingHorizontal: 12, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.primary },
  tabText: { fontSize: 13, color: COLORS.textSecondary, fontWeight: '500' },
  tabTextActive: { color: COLORS.primary, fontWeight: '700' },

  searchBar: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.white, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  filterChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  filterChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  filterChipText: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '500' },
  filterChipTextActive: { color: '#FFF', fontWeight: '700' },
  sortChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, backgroundColor: '#F9FAFB' },
  sortChipActive: { backgroundColor: COLORS.primary + '22' },
  sortChipText: { fontSize: 11, color: COLORS.textSecondary, textTransform: 'capitalize' },
  sortChipTextActive: { color: COLORS.primary, fontWeight: '700' },

  empty: { alignItems: 'center', padding: 40 },
  expertCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  bookingCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  recCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  webinarCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  avatarLg: { width: 50, height: 50, borderRadius: 25, alignItems: 'center', justifyContent: 'center', position: 'relative' },
  onlineDot: { position: 'absolute', bottom: 1, right: 1, width: 12, height: 12, borderRadius: 6, backgroundColor: '#10B981', borderWidth: 2, borderColor: '#FFF' },
  expertName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  expertHeadline: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  metaPill: { fontSize: 11, color: COLORS.textSecondary, paddingHorizontal: 6, paddingVertical: 2, backgroundColor: '#F3F4F6', borderRadius: 4 },
  metaSmall: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  statusPill: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, fontSize: 11, fontWeight: '700', marginTop: 6 },
  tagPill: { fontSize: 11, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, backgroundColor: '#F3F4F6', color: COLORS.textSecondary, fontWeight: '600' },

  btnPrimary: { backgroundColor: COLORS.primary, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  btnPrimaryText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  btnSecondary: { paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  btnSecondaryText: { color: COLORS.textPrimary, fontSize: 13, fontWeight: '600' },
  sectionH: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '85%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
});
