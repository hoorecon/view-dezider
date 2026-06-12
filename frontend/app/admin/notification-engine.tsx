/**
 * /admin/notification-engine — Generic Notification Engine (Super-Admin).
 *
 * CRUD-able notification *triggers*: each binds a registered trigger-event key
 * (e.g. `import-analytics` weekly digest, `import-run-failed` instant alert)
 * to a schedule (daily/weekly/monthly · HH:MM · timezone) or an in-code event,
 * with independent Email (Resend) + WhatsApp (UltraMsg) channel toggles and
 * recipient lists. "Test now" sends immediately. Every dispatch is logged.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Switch, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0', text: '#0F172A',
  muted: '#64748B', primary: '#7C3AED', green: '#059669', red: '#DC2626',
  amber: '#D97706', blue: '#2563EB', chipBg: '#F1F5F9',
};

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_SHORT: Record<string, string> = {
  mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun',
};
const STATUS_COLOR: Record<string, string> = {
  sent: C.green, failed: C.red, error: C.red, skipped_no_recipients: C.amber,
};
const STATUS_LABEL: Record<string, string> = {
  sent: 'SENT', failed: 'FAILED', error: 'ERROR', skipped_no_recipients: 'NO RECIPIENTS',
};

const when = (ts: string | null) => {
  if (!ts) return '—';
  try {
    return new Date(ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z')
      .toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
};

/** Chip-list editor for email addresses / WhatsApp numbers. */
function ChipInput({ values, onChange, placeholder, testIDPrefix, keyboardType }: {
  values: string[]; onChange: (v: string[]) => void; placeholder: string;
  testIDPrefix: string; keyboardType?: any;
}) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    if (!values.includes(v)) onChange([...values, v]);
    setDraft('');
  };
  return (
    <View>
      <View style={st.chipRow}>
        {values.map(v => (
          <View key={v} style={st.recChip} testID={`${testIDPrefix}-chip-${v}`}>
            <Text style={st.recChipTxt}>{v}</Text>
            <TouchableOpacity testID={`${testIDPrefix}-remove-${v}`}
              onPress={() => onChange(values.filter(x => x !== v))}>
              <Ionicons name="close-circle" size={14} color={C.muted} />
            </TouchableOpacity>
          </View>
        ))}
        {!values.length && <Text style={st.emptyInline}>None added yet</Text>}
      </View>
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
        <TextInput
          testID={`${testIDPrefix}-input`}
          style={[st.input, { flex: 1 }]}
          value={draft} onChangeText={setDraft} placeholder={placeholder}
          placeholderTextColor={C.muted} autoCapitalize="none"
          keyboardType={keyboardType} onSubmitEditing={add}
        />
        <TouchableOpacity testID={`${testIDPrefix}-add`} style={st.addBtn} onPress={add}>
          <Ionicons name="add" size={16} color="#FFF" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

export default function AdminNotificationEngineScreen() {
  const { width } = useWindowDimensions();
  const isWide = width >= 1000;

  const [registry, setRegistry] = useState<any[]>([]);
  const [triggers, setTriggers] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // form === null → modal closed; form.id present → edit, absent → create
  const [form, setForm] = useState<any>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [reg, trg, rns] = await Promise.all([
        api.get('/admin/notification-engine/registry'),
        api.get('/admin/notification-engine/triggers'),
        api.get('/admin/notification-engine/runs?limit=20'),
      ]);
      setRegistry(reg.data.events || []);
      setTriggers(trg.data.triggers || []);
      setRuns(rns.data.runs || []);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load notification engine');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const patchTrigger = async (id: string, body: any) => {
    try {
      await api.put(`/admin/notification-engine/triggers/${id}`, body);
      await loadAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Update failed');
    }
  };

  const toggleChannel = (t: any, channel: 'email' | 'whatsapp') => {
    const ch = JSON.parse(JSON.stringify(t.channels || {}));
    ch.email = ch.email || { enabled: false, recipients: [] };
    ch.whatsapp = ch.whatsapp || { enabled: false, numbers: [] };
    ch[channel].enabled = !ch[channel].enabled;
    patchTrigger(t.id, { channels: ch });
  };

  const testNow = async (t: any) => {
    setTesting(t.id);
    try {
      const r = await api.post(`/admin/notification-engine/triggers/${t.id}/test`);
      const rep = r.data.report || {};
      const e = rep.email || {}; const w = rep.whatsapp || {};
      showAlert('Test result',
        r.data.status === 'skipped_no_recipients'
          ? 'Skipped — no recipients configured on enabled channels.'
          : `Status: ${r.data.status.toUpperCase()}\nEmail: ${e.sent || 0}/${e.attempted || 0} sent\nWhatsApp: ${w.sent || 0}/${w.attempted || 0} sent`);
      await loadAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Test send failed');
    } finally { setTesting(null); }
  };

  const removeTrigger = async (t: any) => {
    try {
      await api.delete(`/admin/notification-engine/triggers/${t.id}`);
      showAlert('Deleted', `Trigger "${t.name}" removed.`);
      await loadAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Delete failed');
    }
  };

  const regOf = (key: string) => registry.find(r => r.key === key);

  const openCreate = () => {
    const first = registry[0];
    if (!first) return;
    setForm({
      event_key: first.key,
      name: first.name,
      description: '',
      kind: first.kind,
      enabled: true,
      schedule: first.default_schedule
        ? { ...first.default_schedule }
        : { frequency: 'weekly', day_of_week: 'mon', day_of_month: 1, hour: 9, minute: 0, timezone: 'Asia/Kolkata' },
      channels: { email: { enabled: true, recipients: [] }, whatsapp: { enabled: false, numbers: [] } },
      throttle_minutes: 60,
    });
  };

  const openEdit = (t: any) => {
    setForm({
      id: t.id,
      event_key: t.event_key,
      name: t.name,
      description: t.description || '',
      kind: t.kind,
      enabled: t.enabled,
      schedule: t.schedule
        ? { day_of_month: 1, ...t.schedule }
        : { frequency: 'weekly', day_of_week: 'mon', day_of_month: 1, hour: 9, minute: 0, timezone: 'Asia/Kolkata' },
      channels: JSON.parse(JSON.stringify(t.channels || { email: { enabled: false, recipients: [] }, whatsapp: { enabled: false, numbers: [] } })),
      throttle_minutes: t.throttle_minutes || 60,
    });
  };

  const pickEvent = (key: string) => {
    const r = regOf(key);
    if (!r) return;
    setForm((f: any) => ({
      ...f, event_key: key, kind: r.kind,
      name: f.id ? f.name : r.name,
      schedule: r.default_schedule ? { day_of_month: 1, ...r.default_schedule } : f.schedule,
    }));
  };

  const saveForm = async () => {
    if (!form?.name?.trim() || form.name.trim().length < 2) {
      showAlert('Validation', 'Name must be at least 2 characters.');
      return;
    }
    setSaving(true);
    try {
      const body: any = {
        name: form.name.trim(),
        description: form.description?.trim() || undefined,
        enabled: form.enabled,
        channels: form.channels,
      };
      if (form.kind === 'scheduled') {
        body.schedule = {
          ...form.schedule,
          hour: Math.min(23, Math.max(0, parseInt(String(form.schedule.hour), 10) || 0)),
          minute: Math.min(59, Math.max(0, parseInt(String(form.schedule.minute), 10) || 0)),
          day_of_month: Math.min(28, Math.max(1, parseInt(String(form.schedule.day_of_month), 10) || 1)),
        };
      } else {
        body.throttle_minutes = Math.min(10080, Math.max(1, parseInt(String(form.throttle_minutes), 10) || 60));
      }
      if (form.id) {
        await api.put(`/admin/notification-engine/triggers/${form.id}`, body);
      } else {
        await api.post('/admin/notification-engine/triggers', { ...body, event_key: form.event_key });
      }
      setForm(null);
      await loadAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  if (loading && !triggers.length && !registry.length) {
    return (
      <SafeAreaView style={st.safe} testID="notification-engine-loading">
        <ActivityIndicator size="large" color={C.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.safe} testID="admin-notification-engine-screen">
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        {/* Header */}
        <View style={st.headRow}>
          <View style={{ flex: 1 }}>
            <Text style={st.h1} testID="notification-engine-title">Notification Engine</Text>
            <Text style={st.h1sub}>CRUD trigger events → scheduled digests & instant alerts · Email + WhatsApp</Text>
          </View>
          <TouchableOpacity testID="notification-engine-refresh" style={st.refreshBtn} onPress={loadAll}>
            <Ionicons name="refresh" size={16} color={C.primary} />
          </TouchableOpacity>
          <TouchableOpacity testID="notification-engine-new-trigger" style={st.newBtn} onPress={openCreate}>
            <Ionicons name="add" size={15} color="#FFF" />
            <Text style={st.newBtnTxt}>New Trigger</Text>
          </TouchableOpacity>
        </View>

        {/* Trigger cards */}
        {triggers.map(t => {
          const email = t.channels?.email || {};
          const wa = t.channels?.whatsapp || {};
          return (
            <View key={t.id} style={st.card} testID={`notification-trigger-${t.id}`}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <Text style={st.trigName} numberOfLines={1}>{t.name}</Text>
                    <View style={[st.kindBadge, { backgroundColor: t.kind === 'scheduled' ? '#F3E8FF' : '#FEF3C7' }]}>
                      <Text style={[st.kindBadgeTxt, { color: t.kind === 'scheduled' ? C.primary : C.amber }]}>
                        {t.kind === 'scheduled' ? 'SCHEDULED' : 'EVENT'}
                      </Text>
                    </View>
                    <View style={st.eventChip}>
                      <Text style={st.eventChipTxt}>{t.event_key}</Text>
                    </View>
                  </View>
                  <Text style={st.trigMeta} numberOfLines={1}>
                    {t.schedule_label}
                    {t.kind === 'scheduled' && t.next_run_at ? ` · next: ${when(t.next_run_at)}` : ''}
                    {t.kind === 'event' ? ` · throttle ${t.throttle_minutes || 60}m` : ''}
                  </Text>
                </View>
                <View style={{ alignItems: 'center', gap: 2 }}>
                  <Switch
                    testID={`notification-trigger-enabled-${t.id}`}
                    value={!!t.enabled}
                    onValueChange={(v) => patchTrigger(t.id, { enabled: v })}
                    trackColor={{ false: '#CBD5E1', true: '#C4B5FD' }}
                    thumbColor={t.enabled ? C.primary : '#F1F5F9'}
                  />
                  <Text style={[st.enabledTxt, { color: t.enabled ? C.green : C.muted }]}>
                    {t.enabled ? 'ON' : 'OFF'}
                  </Text>
                </View>
              </View>

              {/* Channels */}
              <View style={st.channelRow}>
                <TouchableOpacity testID={`notification-channel-email-${t.id}`}
                  style={[st.chToggle, email.enabled && st.chToggleOn]}
                  onPress={() => toggleChannel(t, 'email')}>
                  <Ionicons name="mail" size={13} color={email.enabled ? '#FFF' : C.muted} />
                  <Text style={[st.chToggleTxt, email.enabled && { color: '#FFF' }]}>
                    Email {email.enabled ? 'ON' : 'OFF'} ({(email.recipients || []).length})
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity testID={`notification-channel-whatsapp-${t.id}`}
                  style={[st.chToggle, wa.enabled && { backgroundColor: '#059669', borderColor: '#059669' }]}
                  onPress={() => toggleChannel(t, 'whatsapp')}>
                  <Ionicons name="logo-whatsapp" size={13} color={wa.enabled ? '#FFF' : C.muted} />
                  <Text style={[st.chToggleTxt, wa.enabled && { color: '#FFF' }]}>
                    WhatsApp {wa.enabled ? 'ON' : 'OFF'} ({(wa.numbers || []).length})
                  </Text>
                </TouchableOpacity>
                {t.last_status && (
                  <View style={[st.lastRunBadge, { borderColor: (STATUS_COLOR[t.last_status] || C.muted) + '55' }]}>
                    <Text style={[st.lastRunTxt, { color: STATUS_COLOR[t.last_status] || C.muted }]}>
                      last: {STATUS_LABEL[t.last_status] || t.last_status} · {when(t.last_run_at)}
                    </Text>
                  </View>
                )}
              </View>

              {/* Recipients preview */}
              {(email.recipients || []).length + (wa.numbers || []).length > 0 && (
                <View style={[st.chipRow, { marginTop: 8 }]}>
                  {(email.recipients || []).map((r: string) => (
                    <View key={`e-${r}`} style={st.recChip}>
                      <Ionicons name="mail-outline" size={11} color={C.muted} />
                      <Text style={st.recChipTxt}>{r}</Text>
                    </View>
                  ))}
                  {(wa.numbers || []).map((n: string) => (
                    <View key={`w-${n}`} style={[st.recChip, { backgroundColor: '#ECFDF5', borderColor: '#A7F3D0' }]}>
                      <Ionicons name="logo-whatsapp" size={11} color={C.green} />
                      <Text style={st.recChipTxt}>{n}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Actions */}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                <TouchableOpacity testID={`notification-trigger-test-${t.id}`} style={st.testBtn}
                  onPress={() => testNow(t)} disabled={testing === t.id}>
                  {testing === t.id
                    ? <ActivityIndicator size="small" color={C.primary} />
                    : <Ionicons name="paper-plane" size={13} color={C.primary} />}
                  <Text style={st.testBtnTxt}>{testing === t.id ? 'Sending…' : 'Test now'}</Text>
                </TouchableOpacity>
                <TouchableOpacity testID={`notification-trigger-edit-${t.id}`} style={st.editBtn}
                  onPress={() => openEdit(t)}>
                  <Ionicons name="create-outline" size={13} color={C.text} />
                  <Text style={st.editBtnTxt}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity testID={`notification-trigger-delete-${t.id}`} style={st.delBtn}
                  onPress={() => removeTrigger(t)}>
                  <Ionicons name="trash-outline" size={13} color={C.red} />
                  <Text style={st.delBtnTxt}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          );
        })}
        {!triggers.length && (
          <View style={st.card}>
            <Text style={st.empty}>No triggers yet — tap &quot;New Trigger&quot; to create your first one.</Text>
          </View>
        )}

        {/* Run history */}
        <View style={st.card} testID="notification-engine-runs">
          <Text style={st.cardTitle}>Recent dispatches</Text>
          {runs.map(r => {
            const e = r.report?.email || {}; const w = r.report?.whatsapp || {};
            return (
              <View key={r.id} style={st.runRow} testID={`notification-run-${r.id}`}>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={st.runName} numberOfLines={1}>{r.trigger_name || r.event_key}</Text>
                  <Text style={st.runMeta} numberOfLines={1}>
                    {when(r.ts)} · {r.run_kind} · ✉ {e.sent || 0}/{e.attempted || 0} · 💬 {w.sent || 0}/{w.attempted || 0}
                    {r.error ? ` · ${r.error}` : ''}
                  </Text>
                </View>
                <Text style={[st.runStatus, { color: STATUS_COLOR[r.status] || C.muted }]}>
                  {STATUS_LABEL[r.status] || r.status}
                </Text>
              </View>
            );
          })}
          {!runs.length && <Text style={st.empty}>No dispatches yet.</Text>}
        </View>
      </ScrollView>

      {/* Create / Edit modal */}
      <Modal visible={!!form} transparent animationType="fade" onRequestClose={() => setForm(null)}>
        <View style={st.mOverlay}>
          <View style={[st.mBox, { maxWidth: isWide ? 640 : '94%' }]} testID="notification-trigger-modal">
            <View style={st.mHead}>
              <Text style={st.mTitle}>{form?.id ? 'Edit trigger' : 'New trigger'}</Text>
              <TouchableOpacity testID="notification-trigger-modal-close" onPress={() => setForm(null)}>
                <Ionicons name="close" size={20} color={C.muted} />
              </TouchableOpacity>
            </View>
            {form && (
              <ScrollView style={{ maxHeight: 560 }}>
                {/* Event key (create only) */}
                <Text style={st.fLabel}>Trigger event</Text>
                <View style={st.chipRow}>
                  {registry.map(r => (
                    <TouchableOpacity key={r.key} testID={`notification-event-${r.key}`}
                      disabled={!!form.id}
                      style={[st.chip, form.event_key === r.key && st.chipOn, !!form.id && form.event_key !== r.key && { opacity: 0.4 }]}
                      onPress={() => pickEvent(r.key)}>
                      <Text style={[st.chipTxt, form.event_key === r.key && st.chipTxtOn]}>{r.name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <Text style={st.fHint}>{regOf(form.event_key)?.description}</Text>

                <Text style={st.fLabel}>Name</Text>
                <TextInput testID="notification-form-name" style={st.input} value={form.name}
                  onChangeText={(v) => setForm({ ...form, name: v })} placeholder="Trigger name"
                  placeholderTextColor={C.muted} />

                {/* Schedule (scheduled kind) */}
                {form.kind === 'scheduled' ? (
                  <>
                    <Text style={st.fLabel}>Frequency</Text>
                    <View style={st.chipRow}>
                      {['daily', 'weekly', 'monthly'].map(f => (
                        <TouchableOpacity key={f} testID={`notification-freq-${f}`}
                          style={[st.chip, form.schedule.frequency === f && st.chipOn]}
                          onPress={() => setForm({ ...form, schedule: { ...form.schedule, frequency: f } })}>
                          <Text style={[st.chipTxt, form.schedule.frequency === f && st.chipTxtOn]}>
                            {f.charAt(0).toUpperCase() + f.slice(1)}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    {form.schedule.frequency === 'weekly' && (
                      <>
                        <Text style={st.fLabel}>Day of week</Text>
                        <View style={st.chipRow}>
                          {DAYS.map(d => (
                            <TouchableOpacity key={d} testID={`notification-dow-${d}`}
                              style={[st.chip, form.schedule.day_of_week === d && st.chipOn]}
                              onPress={() => setForm({ ...form, schedule: { ...form.schedule, day_of_week: d } })}>
                              <Text style={[st.chipTxt, form.schedule.day_of_week === d && st.chipTxtOn]}>{DAY_SHORT[d]}</Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                      </>
                    )}
                    {form.schedule.frequency === 'monthly' && (
                      <>
                        <Text style={st.fLabel}>Day of month (1–28)</Text>
                        <TextInput testID="notification-form-dom" style={[st.input, { width: 90 }]}
                          value={String(form.schedule.day_of_month ?? 1)} keyboardType="numeric"
                          onChangeText={(v) => setForm({ ...form, schedule: { ...form.schedule, day_of_month: v.replace(/\D/g, '') } })} />
                      </>
                    )}
                    <View style={{ flexDirection: 'row', gap: 10 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={st.fLabel}>Hour (0–23)</Text>
                        <TextInput testID="notification-form-hour" style={st.input}
                          value={String(form.schedule.hour ?? 9)} keyboardType="numeric"
                          onChangeText={(v) => setForm({ ...form, schedule: { ...form.schedule, hour: v.replace(/\D/g, '') } })} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={st.fLabel}>Minute (0–59)</Text>
                        <TextInput testID="notification-form-minute" style={st.input}
                          value={String(form.schedule.minute ?? 0)} keyboardType="numeric"
                          onChangeText={(v) => setForm({ ...form, schedule: { ...form.schedule, minute: v.replace(/\D/g, '') } })} />
                      </View>
                      <View style={{ flex: 2 }}>
                        <Text style={st.fLabel}>Timezone</Text>
                        <TextInput testID="notification-form-timezone" style={st.input}
                          value={form.schedule.timezone} autoCapitalize="none"
                          onChangeText={(v) => setForm({ ...form, schedule: { ...form.schedule, timezone: v } })} />
                      </View>
                    </View>
                  </>
                ) : (
                  <>
                    <Text style={st.fLabel}>Throttle (minutes between alerts)</Text>
                    <TextInput testID="notification-form-throttle" style={[st.input, { width: 120 }]}
                      value={String(form.throttle_minutes ?? 60)} keyboardType="numeric"
                      onChangeText={(v) => setForm({ ...form, throttle_minutes: v.replace(/\D/g, '') })} />
                  </>
                )}

                {/* Email channel */}
                <View style={st.chHead}>
                  <Ionicons name="mail" size={14} color={C.primary} />
                  <Text style={st.chHeadTxt}>Email channel (Resend)</Text>
                  <Switch
                    testID="notification-form-email-enabled"
                    value={!!form.channels.email.enabled}
                    onValueChange={(v) => setForm({ ...form, channels: { ...form.channels, email: { ...form.channels.email, enabled: v } } })}
                    trackColor={{ false: '#CBD5E1', true: '#C4B5FD' }}
                    thumbColor={form.channels.email.enabled ? C.primary : '#F1F5F9'}
                  />
                </View>
                <ChipInput
                  values={form.channels.email.recipients || []}
                  onChange={(v) => setForm({ ...form, channels: { ...form.channels, email: { ...form.channels.email, recipients: v } } })}
                  placeholder="email@company.com" testIDPrefix="notification-email"
                  keyboardType="email-address"
                />

                {/* WhatsApp channel */}
                <View style={st.chHead}>
                  <Ionicons name="logo-whatsapp" size={14} color={C.green} />
                  <Text style={st.chHeadTxt}>WhatsApp channel (UltraMsg)</Text>
                  <Switch
                    testID="notification-form-whatsapp-enabled"
                    value={!!form.channels.whatsapp.enabled}
                    onValueChange={(v) => setForm({ ...form, channels: { ...form.channels, whatsapp: { ...form.channels.whatsapp, enabled: v } } })}
                    trackColor={{ false: '#CBD5E1', true: '#A7F3D0' }}
                    thumbColor={form.channels.whatsapp.enabled ? C.green : '#F1F5F9'}
                  />
                </View>
                <ChipInput
                  values={form.channels.whatsapp.numbers || []}
                  onChange={(v) => setForm({ ...form, channels: { ...form.channels, whatsapp: { ...form.channels.whatsapp, numbers: v } } })}
                  placeholder="919876543210 (country code + number)" testIDPrefix="notification-whatsapp"
                  keyboardType="phone-pad"
                />

                {/* Enabled + Save */}
                <View style={[st.chHead, { marginTop: 16 }]}>
                  <Ionicons name="power" size={14} color={form.enabled ? C.green : C.muted} />
                  <Text style={st.chHeadTxt}>Trigger enabled</Text>
                  <Switch
                    testID="notification-form-enabled"
                    value={!!form.enabled}
                    onValueChange={(v) => setForm({ ...form, enabled: v })}
                    trackColor={{ false: '#CBD5E1', true: '#A7F3D0' }}
                    thumbColor={form.enabled ? C.green : '#F1F5F9'}
                  />
                </View>
                <TouchableOpacity testID="notification-form-save" style={st.saveBtn}
                  onPress={saveForm} disabled={saving}>
                  {saving
                    ? <ActivityIndicator size="small" color="#FFF" />
                    : <Ionicons name="checkmark" size={15} color="#FFF" />}
                  <Text style={st.saveBtnTxt}>{saving ? 'Saving…' : form.id ? 'Save changes' : 'Create trigger'}</Text>
                </TouchableOpacity>
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  headRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 14, gap: 8 },
  h1: { fontSize: 20, fontWeight: '800', color: C.text },
  h1sub: { fontSize: 12, color: C.muted, marginTop: 2 },
  refreshBtn: { padding: 9, borderRadius: 10, backgroundColor: '#F3E8FF' },
  newBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: C.primary, paddingHorizontal: 13, paddingVertical: 9, borderRadius: 10 },
  newBtnTxt: { color: '#FFF', fontSize: 12, fontWeight: '700' },

  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 14 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 10 },
  empty: { fontSize: 12, color: C.muted, paddingVertical: 10, textAlign: 'center' },
  emptyInline: { fontSize: 11, color: C.muted, fontStyle: 'italic', paddingVertical: 4 },

  trigName: { fontSize: 14.5, fontWeight: '800', color: C.text },
  trigMeta: { fontSize: 11.5, color: C.muted, marginTop: 3 },
  kindBadge: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 5 },
  kindBadgeTxt: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  eventChip: { backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.border, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 5 },
  eventChipTxt: { fontSize: 10, fontWeight: '700', color: C.muted, fontFamily: 'monospace' as any },
  enabledTxt: { fontSize: 9, fontWeight: '800', letterSpacing: 0.4 },

  channelRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10, alignItems: 'center' },
  chToggle: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: C.border, backgroundColor: C.chipBg },
  chToggleOn: { backgroundColor: C.primary, borderColor: C.primary },
  chToggleTxt: { fontSize: 11, fontWeight: '700', color: C.muted },
  lastRunBadge: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  lastRunTxt: { fontSize: 10, fontWeight: '700' },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.border },
  chipOn: { backgroundColor: C.primary, borderColor: C.primary },
  chipTxt: { fontSize: 12, color: C.muted, fontWeight: '600' },
  chipTxtOn: { color: '#FFF' },
  recChip: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.border, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 999 },
  recChipTxt: { fontSize: 11, fontWeight: '600', color: C.text },

  testBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#F3E8FF', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 9 },
  testBtnTxt: { color: C.primary, fontSize: 11.5, fontWeight: '800' },
  editBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.border, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 9 },
  editBtnTxt: { color: C.text, fontSize: 11.5, fontWeight: '700' },
  delBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 9 },
  delBtnTxt: { color: C.red, fontSize: 11.5, fontWeight: '700' },

  runRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  runName: { fontSize: 12.5, fontWeight: '700', color: C.text },
  runMeta: { fontSize: 11, color: C.muted, marginTop: 2 },
  runStatus: { fontSize: 10.5, fontWeight: '900', letterSpacing: 0.3 },

  mOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  mBox: { backgroundColor: C.card, borderRadius: 14, padding: 16, width: '100%' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  mTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  fLabel: { fontSize: 11, fontWeight: '800', color: C.muted, textTransform: 'uppercase' as any, letterSpacing: 0.4, marginTop: 12, marginBottom: 6 },
  fHint: { fontSize: 11, color: C.muted, marginTop: 2, lineHeight: 16 },
  input: { borderWidth: 1, borderColor: C.border, borderRadius: 9, paddingHorizontal: 11, paddingVertical: 8, fontSize: 13, color: C.text, backgroundColor: '#FCFCFD' },
  addBtn: { backgroundColor: C.primary, borderRadius: 9, paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center' },
  chHead: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 16, marginBottom: 8 },
  chHeadTxt: { flex: 1, fontSize: 13, fontWeight: '800', color: C.text },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: C.primary, paddingVertical: 11, borderRadius: 10, marginTop: 16 },
  saveBtnTxt: { color: '#FFF', fontSize: 13, fontWeight: '800' },
});
