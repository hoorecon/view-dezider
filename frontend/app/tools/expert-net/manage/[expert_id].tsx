/**
 * /tools/expert-net/manage/[expert_id]  — Expert self-serve dashboard
 *
 * Tabs:
 *   • Inbox      — Incoming bookings: confirm / decline / start-call / recommend / view intake responses
 *   • Schedule   — Availability windows (weekday + start-end-minute + slot length) + blackout dates
 *   • Intake     — Intake form builder (builtin fields OR external URL)
 *   • Webinars   — List my webinars + create new (free or paid, capacity, schedule)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, KeyboardAvoidingView, Platform, Switch,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../../src/utils/api';
import { COLORS } from '../../../../src/constants/colors';
import { showAlert } from '../../../../src/utils/alert';

type Tab = 'inbox' | 'schedule' | 'intake' | 'webinars';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function ExpertManageScreen() {
  const router = useRouter();
  const { expert_id } = useLocalSearchParams();
  const [tab, setTab] = useState<Tab>('inbox');
  const [expert, setExpert] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { (async () => {
    try {
      const r = await api.get(`/expert-net/experts/${expert_id}`);
      setExpert(r.data?.expert);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || e.message);
    } finally { setLoading(false); }
  })(); }, [expert_id]);

  if (loading) {
    return <SafeAreaView style={styles.container}><View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;
  }
  if (!expert) {
    return <SafeAreaView style={styles.container}><View style={styles.center}><Text>Expert not found</Text></View></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4 }}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 10 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>Manage · {expert.name}</Text>
          <Text style={styles.headerSub} numberOfLines={1}>{expert.headline || 'Expert dashboard'}</Text>
        </View>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 12, gap: 6 }} style={styles.tabsRow}>
        {(['inbox', 'schedule', 'intake', 'webinars'] as Tab[]).map(t => (
          <TouchableOpacity key={t} testID={`xnm-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === 'inbox' ? 'Inbox' : t === 'schedule' ? 'Schedule' : t === 'intake' ? 'Intake form' : 'Webinars'}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'inbox' && <InboxTab expertId={String(expert_id)} />}
      {tab === 'schedule' && <ScheduleTab expertId={String(expert_id)} />}
      {tab === 'intake' && <IntakeTab expertId={String(expert_id)} />}
      {tab === 'webinars' && <WebinarsTab expertId={String(expert_id)} expertName={expert.name} />}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// INBOX — incoming bookings as expert
// ---------------------------------------------------------------------------
function InboxTab({ expertId }: { expertId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [picked, setPicked] = useState<any | null>(null);

  const load = useCallback(async () => {
    try { setLoading(true);
      const params: any = { role: 'expert' };
      if (filter !== 'all') params.status = filter;
      const r = await api.get('/expert-net/bookings', { params });
      // Filter to current expert (an account may own multiple experts)
      const mine = (r.data?.items || []).filter((b: any) => b.expert_id === expertId);
      setItems(mine);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [filter, expertId]);
  useEffect(() => { load(); }, [load]);

  const confirm = async (b: any) => {
    try { await api.post(`/expert-net/bookings/${b.booking_id}/confirm`, {}); showAlert('Confirmed', 'Booking confirmed'); load(); }
    catch (e: any) { showAlert('Confirm failed', e?.response?.data?.detail || e.message); }
  };
  const decline = async (b: any) => {
    try { await api.post(`/expert-net/bookings/${b.booking_id}/cancel`, {}); load(); }
    catch (e: any) { showAlert('Decline failed', e?.response?.data?.detail || e.message); }
  };
  const startCall = async (b: any) => {
    try { const r = await api.post(`/expert-net/bookings/${b.booking_id}/start-call`, {});
      router.push(r.data.video_url as any);
    } catch (e: any) { showAlert('Start failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
        {['all', 'pending', 'confirmed', 'in_progress', 'completed', 'cancelled'].map(s => (
          <TouchableOpacity key={s} onPress={() => setFilter(s)} style={[styles.filterChip, filter === s && styles.filterChipActive]}>
            <Text style={[styles.filterChipText, filter === s && styles.filterChipTextActive]}>{s.replace('_', ' ')}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? <ActivityIndicator color={COLORS.primary} /> : items.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="mail-outline" size={36} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No bookings yet</Text>
        </View>
      ) : items.map(b => (
        <View key={b.booking_id} style={styles.card}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>Booking · {(b.user_name || 'User')}</Text>
              <Text style={styles.metaSmall}>{new Date(b.slot_start).toLocaleString()} · {b.duration_minutes}m</Text>
            </View>
            <Text style={[styles.statusPill, statusStyle(b.status)]}>{b.status}</Text>
          </View>

          {!!b.note && <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 6 }}>📝 {b.note}</Text>}
          {!!b.intake_response && Object.keys(b.intake_response).length > 0 && (
            <TouchableOpacity onPress={() => setPicked(b)} style={{ marginTop: 6 }}>
              <Text style={{ fontSize: 12, color: COLORS.primary, fontWeight: '600' }}>View intake answers ({Object.keys(b.intake_response).length})</Text>
            </TouchableOpacity>
          )}

          <View style={{ flexDirection: 'row', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
            {b.status === 'pending' && (
              <>
                <TouchableOpacity testID={`xnm-confirm-${b.booking_id}`} style={[styles.btnPrimary, { flex: 1, minWidth: 100 }]} onPress={() => confirm(b)}>
                  <Ionicons name="checkmark" size={14} color="#FFF" /><Text style={styles.btnPrimaryText}>Confirm</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.btnSecondary, { flex: 1, minWidth: 100 }]} onPress={() => decline(b)}>
                  <Text style={styles.btnSecondaryText}>Decline</Text>
                </TouchableOpacity>
              </>
            )}
            {(b.status === 'confirmed' || b.status === 'in_progress') && (
              <TouchableOpacity style={[styles.btnPrimary, { flex: 1, backgroundColor: '#10B981' }]} onPress={() => startCall(b)}>
                <Ionicons name="videocam" size={14} color="#FFF" /><Text style={styles.btnPrimaryText}>Start call</Text>
              </TouchableOpacity>
            )}
            {b.status !== 'cancelled' && b.status !== 'pending' && (
              <TouchableOpacity testID={`xnm-recommend-${b.booking_id}`} style={[styles.btnSecondary, { flex: 1 }]} onPress={() => router.push({ pathname: '/tools/expert-net/recommend', params: { booking_id: b.booking_id, user_name: b.user_name || '' } } as any)}>
                <Ionicons name="bag-add" size={14} color={COLORS.primary} />
                <Text style={[styles.btnSecondaryText, { color: COLORS.primary }]}> Recommend</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      ))}

      {/* Intake-answers viewer */}
      <Modal visible={!!picked} transparent animationType="slide" onRequestClose={() => setPicked(null)}>
        <View style={styles.overlay}>
          <View style={styles.sheet}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text style={styles.sheetTitle}>Intake answers</Text>
              <TouchableOpacity onPress={() => setPicked(null)}><Ionicons name="close" size={24} /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 400 }}>
              {picked && Object.entries(picked.intake_response || {}).map(([k, v]: any) => (
                <View key={k} style={{ marginBottom: 10 }}>
                  <Text style={styles.fieldLabel}>{k}</Text>
                  <Text style={styles.body}>{Array.isArray(v) ? v.join(', ') : String(v)}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function statusStyle(status: string) {
  if (status === 'confirmed') return { backgroundColor: '#10B98122', color: '#059669' };
  if (status === 'pending') return { backgroundColor: '#F59E0B22', color: '#D97706' };
  if (status === 'in_progress') return { backgroundColor: '#3B82F622', color: '#2563EB' };
  if (status === 'completed') return { backgroundColor: '#6B72801A', color: '#374151' };
  return { backgroundColor: '#EF444422', color: '#DC2626' };
}

// ---------------------------------------------------------------------------
// SCHEDULE — availability editor
// ---------------------------------------------------------------------------
function ScheduleTab({ expertId }: { expertId: string }) {
  const [windows, setWindows] = useState<Array<{ weekday: number; start_minutes: number; end_minutes: number; slot_minutes: number }>>([]);
  const [blackouts, setBlackouts] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { (async () => {
    try {
      const r = await api.get(`/expert-net/experts/${expertId}`);
      const a = r.data?.availability;
      if (a) {
        setWindows(a.windows || []);
        setBlackouts((a.blackout_dates || []).join(', '));
      }
    } finally { setLoading(false); }
  })(); }, [expertId]);

  const addWindow = () => setWindows([...windows, { weekday: 1, start_minutes: 9 * 60, end_minutes: 17 * 60, slot_minutes: 30 }]);
  const updateWindow = (i: number, patch: any) => {
    const next = [...windows];
    next[i] = { ...next[i], ...patch };
    setWindows(next);
  };
  const removeWindow = (i: number) => setWindows(windows.filter((_, idx) => idx !== i));

  const save = async () => {
    try { setSaving(true);
      await api.put(`/expert-net/experts/${expertId}/availability`, {
        windows,
        blackout_dates: blackouts.split(',').map(s => s.trim()).filter(Boolean),
      });
      showAlert('Saved', 'Availability updated');
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  if (loading) return <View style={{ padding: 32 }}><ActivityIndicator color={COLORS.primary} /></View>;

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <View style={styles.card}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={styles.sectionH}>Weekly windows</Text>
          <TouchableOpacity onPress={addWindow} style={styles.btnSmall}>
            <Ionicons name="add" size={14} color="#FFF" /><Text style={styles.btnSmallText}>Add window</Text>
          </TouchableOpacity>
        </View>
        {windows.length === 0 && <Text style={{ color: COLORS.textMuted, fontSize: 12, marginTop: 8 }}>Tap "Add window" to define when you accept bookings.</Text>}
        {windows.map((w, i) => (
          <View key={i} style={styles.windowCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={styles.fieldLabel}>Day</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: 'row', gap: 4 }}>
                  {WEEKDAYS.map((d, idx) => (
                    <TouchableOpacity key={d} onPress={() => updateWindow(i, { weekday: idx })} style={[styles.chip, w.weekday === idx && styles.chipActive]}>
                      <Text style={[styles.chipText, w.weekday === idx && styles.chipTextActive]}>{d}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            </View>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Start (HH:MM)</Text>
                <TextInput style={styles.input} value={fmtMin(w.start_minutes)} onChangeText={v => updateWindow(i, { start_minutes: parseMin(v) })} placeholder="09:00" placeholderTextColor={COLORS.textMuted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>End (HH:MM)</Text>
                <TextInput style={styles.input} value={fmtMin(w.end_minutes)} onChangeText={v => updateWindow(i, { end_minutes: parseMin(v) })} placeholder="17:00" placeholderTextColor={COLORS.textMuted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Slot (min)</Text>
                <TextInput style={styles.input} value={String(w.slot_minutes)} onChangeText={v => updateWindow(i, { slot_minutes: Math.max(10, Math.min(240, parseInt(v, 10) || 30)) })} keyboardType="numeric" />
              </View>
            </View>
            <TouchableOpacity onPress={() => removeWindow(i)} style={{ alignSelf: 'flex-end', marginTop: 6 }}>
              <Text style={{ color: '#DC2626', fontSize: 12, fontWeight: '600' }}>Remove</Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionH}>Blackout dates</Text>
        <Text style={{ color: COLORS.textMuted, fontSize: 11, marginTop: 4 }}>Comma-separated YYYY-MM-DD. Bookings won't be allowed on these days.</Text>
        <TextInput style={[styles.input, { marginTop: 6 }]} value={blackouts} onChangeText={setBlackouts} placeholder="2026-12-25, 2027-01-01" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
      </View>

      <TouchableOpacity testID="xnm-save-availability" onPress={save} disabled={saving} style={[styles.btnPrimary, { marginTop: 8, opacity: saving ? 0.6 : 1 }]}>
        {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Save availability</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
}

function fmtMin(min: number): string {
  const h = Math.floor(min / 60).toString().padStart(2, '0');
  const m = (min % 60).toString().padStart(2, '0');
  return `${h}:${m}`;
}
function parseMin(s: string): number {
  const m = (s || '').match(/^(\d{1,2}):?(\d{0,2})$/);
  if (!m) return 0;
  return Math.min(24 * 60, parseInt(m[1], 10) * 60 + (parseInt(m[2] || '0', 10) || 0));
}

// ---------------------------------------------------------------------------
// INTAKE — form builder
// ---------------------------------------------------------------------------
const FIELD_TYPES = ['short_text', 'long_text', 'single_select', 'multi_select', 'number', 'consent'];

function IntakeTab({ expertId }: { expertId: string }) {
  const [mode, setMode] = useState<'builtin' | 'external'>('builtin');
  const [title, setTitle] = useState('Pre-session intake');
  const [description, setDescription] = useState('');
  const [externalUrl, setExternalUrl] = useState('');
  const [requiredBefore, setRequiredBefore] = useState(true);
  const [fields, setFields] = useState<Array<any>>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { (async () => {
    try {
      const r = await api.get(`/expert-net/experts/${expertId}`);
      const f = r.data?.intake_form;
      if (f) {
        setMode(f.mode || 'builtin');
        setTitle(f.title || 'Pre-session intake');
        setDescription(f.description || '');
        setExternalUrl(f.external_url || '');
        setFields(f.fields || []);
        setRequiredBefore(f.is_required_before_booking !== false);
      }
    } finally { setLoading(false); }
  })(); }, [expertId]);

  const addField = () => setFields([...fields, { field_id: `f_${Date.now()}`, label: 'New question', field_type: 'short_text', required: false }]);
  const updateField = (i: number, patch: any) => {
    const next = [...fields];
    next[i] = { ...next[i], ...patch };
    setFields(next);
  };
  const removeField = (i: number) => setFields(fields.filter((_, idx) => idx !== i));

  const save = async () => {
    if (mode === 'external' && !externalUrl.trim()) {
      return showAlert('Required', 'External URL is required when mode = external');
    }
    if (mode === 'builtin' && fields.length === 0) {
      return showAlert('Required', 'Add at least one field for the built-in form');
    }
    try { setSaving(true);
      await api.put(`/expert-net/experts/${expertId}/intake-form`, {
        title, description: description || undefined,
        mode,
        external_url: mode === 'external' ? externalUrl : undefined,
        fields: mode === 'builtin' ? fields.map(f => ({
          ...f,
          options: f.options ? (typeof f.options === 'string' ? f.options.split(',').map((s: string) => s.trim()).filter(Boolean) : f.options) : undefined,
        })) : [],
        is_required_before_booking: requiredBefore,
      });
      showAlert('Saved', 'Intake form updated');
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  if (loading) return <View style={{ padding: 32 }}><ActivityIndicator color={COLORS.primary} /></View>;

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <View style={styles.card}>
        <Text style={styles.sectionH}>Form mode</Text>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
          <TouchableOpacity onPress={() => setMode('builtin')} style={[styles.chip, mode === 'builtin' && styles.chipActive]}>
            <Text style={[styles.chipText, mode === 'builtin' && styles.chipTextActive]}>Built-in</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setMode('external')} style={[styles.chip, mode === 'external' && styles.chipActive]}>
            <Text style={[styles.chipText, mode === 'external' && styles.chipTextActive]}>External URL (Google Form / Typeform)</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.fieldLabel}>Title *</Text>
        <TextInput style={styles.input} value={title} onChangeText={setTitle} />
        <Text style={styles.fieldLabel}>Description</Text>
        <TextInput style={[styles.input, { minHeight: 60 }]} multiline value={description} onChangeText={setDescription} placeholderTextColor={COLORS.textMuted} />

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <Switch value={requiredBefore} onValueChange={setRequiredBefore} />
          <Text style={{ color: COLORS.textPrimary, fontSize: 12 }}>Require completion before booking</Text>
        </View>
      </View>

      {mode === 'external' ? (
        <View style={styles.card}>
          <Text style={styles.sectionH}>External form URL</Text>
          <TextInput style={styles.input} value={externalUrl} onChangeText={setExternalUrl} placeholder="https://forms.gle/abc123" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
        </View>
      ) : (
        <View style={styles.card}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={styles.sectionH}>Fields</Text>
            <TouchableOpacity onPress={addField} style={styles.btnSmall}>
              <Ionicons name="add" size={14} color="#FFF" /><Text style={styles.btnSmallText}>Add field</Text>
            </TouchableOpacity>
          </View>
          {fields.map((f, i) => (
            <View key={i} style={styles.windowCard}>
              <Text style={styles.fieldLabel}>Field id (no spaces)</Text>
              <TextInput style={styles.input} value={f.field_id} onChangeText={v => updateField(i, { field_id: v.replace(/[^a-z0-9_]/gi, '').toLowerCase() })} autoCapitalize="none" />
              <Text style={styles.fieldLabel}>Label *</Text>
              <TextInput style={styles.input} value={f.label} onChangeText={v => updateField(i, { label: v })} />
              <Text style={styles.fieldLabel}>Type</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: 'row', gap: 4 }}>
                  {FIELD_TYPES.map(t => (
                    <TouchableOpacity key={t} onPress={() => updateField(i, { field_type: t })} style={[styles.chip, f.field_type === t && styles.chipActive]}>
                      <Text style={[styles.chipText, f.field_type === t && styles.chipTextActive]}>{t}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
              {(f.field_type === 'single_select' || f.field_type === 'multi_select') && (
                <>
                  <Text style={styles.fieldLabel}>Options (comma-separated)</Text>
                  <TextInput style={styles.input} value={Array.isArray(f.options) ? f.options.join(', ') : (f.options || '')} onChangeText={v => updateField(i, { options: v })} placeholder="Option 1, Option 2" placeholderTextColor={COLORS.textMuted} />
                </>
              )}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Switch value={!!f.required} onValueChange={v => updateField(i, { required: v })} />
                  <Text style={{ color: COLORS.textPrimary, fontSize: 12 }}>Required</Text>
                </View>
                <TouchableOpacity onPress={() => removeField(i)}><Text style={{ color: '#DC2626', fontSize: 12, fontWeight: '600' }}>Remove field</Text></TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      )}

      <TouchableOpacity testID="xnm-save-intake" onPress={save} disabled={saving} style={[styles.btnPrimary, { marginTop: 8, opacity: saving ? 0.6 : 1 }]}>
        {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Save intake form</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// WEBINARS — list + create
// ---------------------------------------------------------------------------
function WebinarsTab({ expertId, expertName }: { expertId: string; expertName?: string }) {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/expert-net/webinars', { params: { upcoming_only: false } });
      const mine = (r.data?.items || []).filter((w: any) => w.expert_id === expertId);
      setItems(mine);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [expertId]);
  useEffect(() => { load(); }, [load]);

  const startWebinar = async (w: any) => {
    try { const r = await api.post(`/expert-net/webinars/${w.webinar_id}/start`, {});
      router.push(r.data.video_url as any);
    } catch (e: any) { showAlert('Start failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
      <TouchableOpacity testID="xnm-create-webinar" style={[styles.btnPrimary, { marginBottom: 14 }]} onPress={() => setShowCreate(true)}>
        <Ionicons name="add" size={16} color="#FFF" /><Text style={styles.btnPrimaryText}>Create webinar</Text>
      </TouchableOpacity>

      {loading ? <ActivityIndicator color={COLORS.primary} /> : items.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="megaphone-outline" size={36} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No webinars yet</Text>
        </View>
      ) : items.map(w => (
        <View key={w.webinar_id} style={styles.card}>
          <Text style={styles.cardTitle}>{w.title}</Text>
          <Text style={styles.metaSmall}>{new Date(w.starts_at).toLocaleString()} · {w.duration_minutes}m</Text>
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
            <Text style={[styles.tagPill, { backgroundColor: w.is_free ? '#10B98122' : '#F59E0B22', color: w.is_free ? '#059669' : '#D97706' }]}>{w.is_free ? 'Free' : `₹${w.price_inr}`}</Text>
            <Text style={styles.tagPill}>{w.registered_count || 0} reg</Text>
            {w.capacity ? <Text style={styles.tagPill}>cap {w.capacity}</Text> : null}
            <Text style={[styles.tagPill, statusStyle(w.status)]}>{w.status}</Text>
          </View>
          {(w.status === 'scheduled' || w.status === 'live') && (
            <TouchableOpacity style={[styles.btnPrimary, { marginTop: 10, backgroundColor: '#10B981' }]} onPress={() => startWebinar(w)}>
              <Ionicons name="videocam" size={14} color="#FFF" /><Text style={styles.btnPrimaryText}>{w.status === 'live' ? 'Resume' : 'Go live'}</Text>
            </TouchableOpacity>
          )}
        </View>
      ))}

      {showCreate && <CreateWebinarSheet expertId={expertId} expertName={expertName} onClose={() => { setShowCreate(false); load(); }} />}
    </ScrollView>
  );
}

function CreateWebinarSheet({ expertId, expertName, onClose }: { expertId: string; expertName?: string; onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startsAt, setStartsAt] = useState(() => {
    const d = new Date(); d.setHours(d.getHours() + 24); d.setMinutes(0, 0, 0);
    return d.toISOString().slice(0, 16); // yyyy-mm-ddTHH:MM (no seconds)
  });
  const [duration, setDuration] = useState('60');
  const [isFree, setIsFree] = useState(true);
  const [price, setPrice] = useState('0');
  const [capacity, setCapacity] = useState('100');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim()) return showAlert('Required', 'Title is required');
    try { setBusy(true);
      const iso = new Date(startsAt).toISOString();
      await api.post('/expert-net/webinars', {
        title, description: description || undefined,
        starts_at_iso: iso,
        duration_minutes: parseInt(duration, 10) || 60,
        is_free: isFree, price_inr: isFree ? 0 : (parseInt(price, 10) || 0),
        capacity: capacity ? parseInt(capacity, 10) : undefined,
        language: 'en',
      });
      showAlert('Created', 'Webinar scheduled');
      onClose();
    } catch (e: any) { showAlert('Create failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Text style={styles.sheetTitle}>Create webinar</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
          </View>
          <ScrollView style={{ maxHeight: 480 }}>
            <Text style={styles.fieldLabel}>Title *</Text>
            <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder="Mastering Salary Negotiation" placeholderTextColor={COLORS.textMuted} />
            <Text style={styles.fieldLabel}>Description</Text>
            <TextInput style={[styles.input, { minHeight: 70 }]} multiline value={description} onChangeText={setDescription} placeholder="What you'll learn…" placeholderTextColor={COLORS.textMuted} />

            <Text style={styles.fieldLabel}>Starts at (yyyy-MM-ddTHH:MM)</Text>
            <TextInput style={styles.input} value={startsAt} onChangeText={setStartsAt} autoCapitalize="none" placeholderTextColor={COLORS.textMuted} />

            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Duration (min)</Text>
                <TextInput style={styles.input} keyboardType="numeric" value={duration} onChangeText={setDuration} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Capacity</Text>
                <TextInput style={styles.input} keyboardType="numeric" value={capacity} onChangeText={setCapacity} />
              </View>
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
              <Switch value={isFree} onValueChange={setIsFree} />
              <Text style={{ color: COLORS.textPrimary, fontSize: 13 }}>Free webinar</Text>
            </View>
            {!isFree && (
              <>
                <Text style={styles.fieldLabel}>Price (INR)</Text>
                <TextInput style={styles.input} keyboardType="numeric" value={price} onChangeText={setPrice} placeholder="499" placeholderTextColor={COLORS.textMuted} />
              </>
            )}
          </ScrollView>

          <TouchableOpacity testID="xnm-submit-webinar" onPress={submit} disabled={busy} style={[styles.btnPrimary, { marginTop: 14, opacity: busy ? 0.6 : 1 }]}>
            {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnPrimaryText}>Create</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// styles
// ---------------------------------------------------------------------------
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  headerTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  headerSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },

  tabsRow: { backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider, maxHeight: 46 },
  tab: { paddingHorizontal: 14, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.primary },
  tabText: { fontSize: 13, color: COLORS.textSecondary, fontWeight: '500' },
  tabTextActive: { color: COLORS.primary, fontWeight: '700' },

  card: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  sectionH: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  body: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  metaSmall: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  empty: { alignItems: 'center', padding: 40 },

  filterChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  filterChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  filterChipText: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '500', textTransform: 'capitalize' },
  filterChipTextActive: { color: '#FFF', fontWeight: '700' },

  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  chipActive: { backgroundColor: COLORS.primary + '22', borderColor: COLORS.primary },
  chipText: { fontSize: 11, color: COLORS.textSecondary },
  chipTextActive: { color: COLORS.primary, fontWeight: '700' },

  windowCard: { backgroundColor: '#FAFAFA', borderRadius: 8, padding: 10, marginTop: 10, borderWidth: 1, borderColor: COLORS.divider },

  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },

  statusPill: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  tagPill: { fontSize: 11, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, backgroundColor: '#F3F4F6', color: COLORS.textSecondary, fontWeight: '600' },

  btnPrimary: { backgroundColor: COLORS.primary, paddingVertical: 11, paddingHorizontal: 14, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  btnPrimaryText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  btnSecondary: { paddingVertical: 11, paddingHorizontal: 14, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  btnSecondaryText: { color: COLORS.textPrimary, fontSize: 13, fontWeight: '600' },
  btnSmall: { backgroundColor: COLORS.primary, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, flexDirection: 'row', alignItems: 'center', gap: 4 },
  btnSmallText: { color: '#FFF', fontSize: 11, fontWeight: '700' },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '92%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
});
