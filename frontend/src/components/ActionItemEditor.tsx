/**
 * ActionItemEditor — universal embeddable Action-Plan UI.
 *
 * Usage:
 *   <ActionItemEditor
 *     sourceModule="PROS_CONS"
 *     sourceId={analysisId}
 *     sourceLabel={`Pros & Cons · ${title}`}
 *     defaultLifeArea={lifeArea}
 *   />
 *
 * Captures Who / What / By When + recurrence + priority, lists items for
 * the given source, lets the user PORT each one into CTT (one-shot) or
 * LifeStyle (recurring). Backed by /api/action-items/*.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView,
  ActivityIndicator, Modal, Platform, Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';
import { showAlert } from '../utils/alert';
import { formatDMY } from '../utils/datetime';

/** Mask free text into a DD-MM-YYYY shape as the user types. */
function maskDMY(text: string): string {
  const d = text.replace(/\D/g, '').slice(0, 8);
  if (d.length > 4) return `${d.slice(0, 2)}-${d.slice(2, 4)}-${d.slice(4)}`;
  if (d.length > 2) return `${d.slice(0, 2)}-${d.slice(2)}`;
  return d;
}

/** Convert a DD-MM-YYYY string to a sortable YYYY-MM-DD (or null if invalid). */
function dmyToISO(s: string): string | null {
  const m = s.trim().match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (!m) return null;
  const dd = +m[1], mm = +m[2];
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) return null;
  const iso = `${m[3]}-${m[2]}-${m[1]}`;
  return isNaN(new Date(`${iso}T00:00:00`).getTime()) ? null : iso;
}

type ActionItem = {
  action_id: string;
  source_module: string;
  source_id?: string|null;
  source_label?: string|null;
  source_subref?: string|null;
  title: string;
  who: string;
  by_when?: string|null;
  recurrence_type: 'one_time'|'recurring';
  recurrence_frequency?: string|null;
  recurrence_time?: string|null;
  priority: 'low'|'medium'|'high'|'urgent';
  status: string;
  progress_pct: number;
  life_area?: string|null;
  notes?: string;
  ported_to?: 'CTT'|'LIFESTYLE'|null;
  ported_ref_id?: string|null;
  ported_at?: string|null;
  assignee_email?: string;
  assignee_mobile?: string;
  description?: string;
  is_mpps?: boolean;
};

interface Props {
  sourceModule: string;
  sourceId?: string;
  sourceLabel?: string;
  sourceSubref?: string;
  defaultLifeArea?: string;
  // When true, hides the "Add Action Item" controls (used in read-only contexts)
  readOnly?: boolean;
  // Optional callback after a successful add/port
  onChange?: (items: ActionItem[]) => void;
  title?: string; // section title override
}

const PRIORITY_OPTS: Array<{ id: ActionItem['priority']; label: string; color: string }> = [
  { id: 'low',    label: 'Low',    color: '#94A3B8' },
  { id: 'medium', label: 'Medium', color: '#3B82F6' },
  { id: 'high',   label: 'High',   color: '#F59E0B' },
  { id: 'urgent', label: 'Urgent', color: '#EF4444' },
];

const STATUS_OPTS: Array<{ id: string; label: string; color: string }> = [
  { id: 'pending',     label: 'Pending',     color: '#94A3B8' },
  { id: 'in_progress', label: 'In Progress', color: '#3B82F6' },
  { id: 'done',        label: 'Done',        color: '#10B981' },
  { id: 'blocked',     label: 'Blocked',     color: '#EF4444' },
];

const FREQ_OPTS = ['daily','weekly','biweekly','monthly','quarterly','yearly'];

export default function ActionItemEditor(props: Props) {
  const router = useRouter();
  const { sourceModule, sourceId, sourceLabel, sourceSubref, defaultLifeArea, readOnly, onChange } = props;

  const [items, setItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<ActionItem|null>(null);
  const [savingId, setSavingId] = useState<string|null>(null);

  // Add-form state
  const [fTitle, setFTitle] = useState('');
  const [fWho, setFWho] = useState('');
  const [fByWhen, setFByWhen] = useState('');
  const [fPriority, setFPriority] = useState<ActionItem['priority']>('medium');
  const [fRecurring, setFRecurring] = useState(false);
  const [fFreq, setFFreq] = useState('weekly');
  const [fTime, setFTime] = useState('');
  const [fNotes, setFNotes] = useState('');

  const resetForm = () => {
    setFTitle(''); setFWho(''); setFByWhen(''); setFPriority('medium');
    setFRecurring(false); setFFreq('weekly'); setFTime(''); setFNotes('');
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q: any = { source_module: sourceModule };
      if (sourceId) q.source_id = sourceId;
      if (sourceSubref) q.source_subref = sourceSubref;
      const qs = new URLSearchParams(q).toString();
      const r = await api.get(`/action-items?${qs}`);
      setItems(r.data || []);
      onChange?.(r.data || []);
    } catch (e) { console.warn('ActionItems load', e); }
    finally { setLoading(false); }
  }, [sourceModule, sourceId, sourceSubref]);

  useEffect(() => { load(); }, [load]);

  const submitNew = async () => {
    if (!fTitle.trim()) return showAlert('Required', 'Action description (What) is required.');
    const byWhenIso = fByWhen.trim() ? dmyToISO(fByWhen.trim()) : null;
    if (fByWhen.trim() && !byWhenIso) {
      return showAlert('Invalid date', 'Enter the date as DD-MM-YYYY (e.g. 30-08-2026).');
    }
    try {
      const payload: any = {
        source_module: sourceModule,
        source_id: sourceId,
        source_label: sourceLabel,
        source_subref: sourceSubref,
        title: fTitle.trim(),
        who: fWho.trim(),
        by_when: byWhenIso,
        priority: fPriority,
        recurrence_type: fRecurring ? 'recurring' : 'one_time',
        recurrence_frequency: fRecurring ? fFreq : null,
        recurrence_time: fRecurring ? (fTime || null) : null,
        life_area: defaultLifeArea || null,
        notes: fNotes,
      };
      if (editing) {
        await api.put(`/action-items/${editing.action_id}`, payload);
      } else {
        await api.post('/action-items', payload);
      }
      setAddOpen(false); setEditing(null); resetForm(); load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    }
  };

  const openEdit = (it: ActionItem) => {
    setEditing(it);
    setFTitle(it.title || ''); setFWho(it.who || '');
    setFByWhen(it.by_when ? formatDMY(it.by_when) : ''); setFPriority(it.priority);
    setFRecurring(it.recurrence_type === 'recurring');
    setFFreq(it.recurrence_frequency || 'weekly');
    setFTime(it.recurrence_time || '');
    setFNotes(it.notes || '');
    setAddOpen(true);
  };

  const portTo = async (it: ActionItem, target: 'CTT'|'LIFESTYLE') => {
    if (it.ported_to) {
      return showAlert('Already ported', `This item is already in ${it.ported_to}.`);
    }
    setSavingId(it.action_id);
    try {
      const path = target === 'CTT' ? 'port-to-ctt' : 'port-to-lifestyle';
      await api.post(`/action-items/${it.action_id}/${path}`);
      showAlert('Ported', `Action item added to ${target === 'CTT' ? 'CTT' : 'LifeStyle'}.`);
      load();
    } catch (e: any) {
      showAlert('Could not port', e?.response?.data?.detail || 'Try again');
    } finally { setSavingId(null); }
  };

  const updateStatus = async (it: ActionItem, status: string) => {
    setSavingId(it.action_id);
    try {
      await api.put(`/action-items/${it.action_id}`, { status });
      load();
    } catch { /* ignore */ } finally { setSavingId(null); }
  };

  const removeItem = async (it: ActionItem) => {
    showAlert('Cancel this action?', `${it.title}`, [
      { text: 'Keep', style: 'cancel' },
      { text: 'Cancel item', style: 'destructive', onPress: async () => {
        try { await api.delete(`/action-items/${it.action_id}`); load(); }
        catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
      } },
    ]);
  };

  return (
    <View style={s.box}>
      <View style={s.head}>
        <Ionicons name="checkmark-done-circle" size={18} color="#0D9488" />
        <Text style={s.title}>{props.title || 'Action Plan'}</Text>
        <View style={s.countPill}><Text style={s.countText}>{items.length}</Text></View>
        {!readOnly && (
          <TouchableOpacity style={s.addBtn} onPress={() => { setEditing(null); resetForm(); setAddOpen(true); }}>
            <Ionicons name="add" size={14} color="#FFF" />
            <Text style={s.addBtnText}>Add</Text>
          </TouchableOpacity>
        )}
      </View>

      <Text style={s.helper}>
        Who · What · By when. One-time items can be ported to <Text style={s.helperBold}>CTT</Text> for tracking; recurring items to <Text style={s.helperBold}>LifeStyle</Text>.
      </Text>

      {loading ? (
        <ActivityIndicator color="#0D9488" style={{ marginVertical: 12 }} />
      ) : items.length === 0 ? (
        <Text style={s.empty}>No action items yet. Capture concrete next steps here.</Text>
      ) : items.map((it, idx) => {
        const pri = PRIORITY_OPTS.find(p => p.id === it.priority) || PRIORITY_OPTS[1];
        const st  = STATUS_OPTS.find(p => p.id === it.status) || STATUS_OPTS[0];
        return (
          <View key={it.action_id} style={s.row}>
            <View style={[s.priDot, { backgroundColor: pri.color }]} />
            <View style={{ flex: 1 }}>
              <Text style={s.rowTitle} numberOfLines={2}>
                <Text style={s.serialNo}>{idx + 1}. </Text>{it.title}
              </Text>
              <View style={s.metaRow}>
                {!!it.who && <Text style={s.metaText}>👤 {it.who}</Text>}
                {!!it.by_when && <Text style={s.metaText}>📅 {formatDMY(it.by_when)}</Text>}
                <Text style={s.metaText}>{it.recurrence_type === 'recurring' ? `🔁 ${it.recurrence_frequency}${it.recurrence_time ? ` @ ${it.recurrence_time}` : ''}` : '⚡ one-time'}</Text>
              </View>
              <View style={s.chipsRow}>
                {STATUS_OPTS.map(opt => {
                  const active = it.status === opt.id;
                  return (
                    <TouchableOpacity key={opt.id} style={[s.chip, active && { backgroundColor: opt.color, borderColor: opt.color }]} onPress={() => updateStatus(it, opt.id)}>
                      <Text style={[s.chipText, active && { color: '#FFF' }]}>{opt.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <View style={s.actionsRow}>
                {it.ported_to ? (
                  <TouchableOpacity
                    style={[s.portedPill, { backgroundColor: it.ported_to === 'CTT' ? '#DBEAFE' : '#FEF3C7' }]}
                    onPress={() => router.push((it.ported_to === 'CTT' ? '/tools/ctt' : '/tools/lifestyle') as any)}
                    accessibilityLabel={`Open in ${it.ported_to === 'CTT' ? 'CTT' : 'LifeStyle'}`}
                  >
                    <Ionicons name="link" size={12} color={it.ported_to === 'CTT' ? '#1D4ED8' : '#B45309'} />
                    <Text style={[s.portedText, { color: it.ported_to === 'CTT' ? '#1D4ED8' : '#B45309' }]}>
                      In {it.ported_to === 'CTT' ? 'CTT' : 'LifeStyle'}
                    </Text>
                    <Ionicons name="open-outline" size={12} color={it.ported_to === 'CTT' ? '#1D4ED8' : '#B45309'} />
                  </TouchableOpacity>
                ) : (
                  <>
                    <TouchableOpacity style={[s.portBtn, { backgroundColor: '#DBEAFE' }]} onPress={() => portTo(it, 'CTT')} disabled={savingId === it.action_id}>
                      <Ionicons name="calendar" size={12} color="#1D4ED8" />
                      <Text style={[s.portBtnText, { color: '#1D4ED8' }]}>→ CTT</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.portBtn, { backgroundColor: '#FEF3C7' }]} onPress={() => portTo(it, 'LIFESTYLE')} disabled={savingId === it.action_id}>
                      <Ionicons name="repeat" size={12} color="#B45309" />
                      <Text style={[s.portBtnText, { color: '#B45309' }]}>→ LifeStyle</Text>
                    </TouchableOpacity>
                  </>
                )}
                {!readOnly && (
                  <>
                    <TouchableOpacity style={s.iconBtn} onPress={() => openEdit(it)}>
                      <Ionicons name="create-outline" size={14} color="#475569" />
                    </TouchableOpacity>
                    <TouchableOpacity style={s.iconBtn} onPress={() => removeItem(it)}>
                      <Ionicons name="trash-outline" size={14} color="#DC2626" />
                    </TouchableOpacity>
                  </>
                )}
              </View>
            </View>
          </View>
        );
      })}

      {/* Add/Edit modal */}
      <Modal visible={addOpen} transparent animationType="slide" onRequestClose={() => { setAddOpen(false); setEditing(null); }}>
        <View style={s.overlay}>
          <View style={s.modal}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>{editing ? 'Edit Action Item' : 'New Action Item'}</Text>
              <TouchableOpacity onPress={() => { setAddOpen(false); setEditing(null); }}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 520 }}>
              <Text style={s.label}>What * <Text style={s.hint}>(action description)</Text></Text>
              <TextInput style={s.input} value={fTitle} onChangeText={setFTitle} placeholder="e.g. Email vendor to negotiate price" placeholderTextColor="#9CA3AF" />

              <Text style={s.label}>Who <Text style={s.hint}>(assignee name)</Text></Text>
              <TextInput style={s.input} value={fWho} onChangeText={setFWho} placeholder="Self / Jane Doe / Team A" placeholderTextColor="#9CA3AF" />

              <Text style={s.label}>By When <Text style={s.hint}>(DD-MM-YYYY)</Text></Text>
              <TextInput style={s.input} value={fByWhen} onChangeText={t => setFByWhen(maskDMY(t))} placeholder="30-08-2026" placeholderTextColor="#9CA3AF" keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'default'} />

              <Text style={s.label}>Priority</Text>
              <View style={s.chipsRow}>
                {PRIORITY_OPTS.map(p => (
                  <TouchableOpacity key={p.id} style={[s.chip, fPriority === p.id && { backgroundColor: p.color, borderColor: p.color }]} onPress={() => setFPriority(p.id)}>
                    <Text style={[s.chipText, fPriority === p.id && { color: '#FFF' }]}>{p.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <View style={s.recurRow}>
                <Text style={s.label}>Recurring routine?</Text>
                <Switch value={fRecurring} onValueChange={setFRecurring} trackColor={{ false: '#CBD5E1', true: '#F59E0B' }} />
              </View>
              {fRecurring && (
                <>
                  <Text style={s.label}>Frequency</Text>
                  <View style={s.chipsRow}>
                    {FREQ_OPTS.map(f => (
                      <TouchableOpacity key={f} style={[s.chip, fFreq === f && { backgroundColor: '#F59E0B', borderColor: '#F59E0B' }]} onPress={() => setFFreq(f)}>
                        <Text style={[s.chipText, fFreq === f && { color: '#FFF' }]}>{f}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  <Text style={s.label}>Time of day <Text style={s.hint}>(HH:MM, optional)</Text></Text>
                  <TextInput style={s.input} value={fTime} onChangeText={setFTime} placeholder="07:00" placeholderTextColor="#9CA3AF" />
                </>
              )}

              <Text style={s.label}>Notes</Text>
              <TextInput style={[s.input, { height: 70 }]} value={fNotes} onChangeText={setFNotes} placeholder="Optional notes…" placeholderTextColor="#9CA3AF" multiline />
            </ScrollView>
            <View style={s.modalFoot}>
              <TouchableOpacity style={s.cancelBtn} onPress={() => { setAddOpen(false); setEditing(null); }}>
                <Text style={s.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.saveBtn} onPress={submitNew}>
                <Ionicons name="checkmark" size={16} color="#FFF" />
                <Text style={s.saveBtnText}>{editing ? 'Update' : 'Add'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  box: { marginTop: 16, padding: 14, borderRadius: 12, backgroundColor: '#F0FDFA', borderWidth: 1, borderColor: '#A7F3D0' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 15, fontWeight: '800', color: '#065F46', flex: 1 },
  countPill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, backgroundColor: '#CCFBF1' },
  countText: { fontSize: 11, fontWeight: '700', color: '#065F46' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0D9488', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  addBtnText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },

  helper: { fontSize: 11, color: '#065F46', marginTop: 4, lineHeight: 15 },
  helperBold: { fontWeight: '700' },

  empty: { fontSize: 12, color: '#64748B', fontStyle: 'italic', paddingVertical: 12 },

  row: { flexDirection: 'row', gap: 8, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#CCFBF1' },
  priDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  rowTitle: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  serialNo: { color: '#0D9488', fontWeight: '800' },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  metaText: { fontSize: 11, color: '#475569' },

  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  chip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFFFFF' },
  chipText: { fontSize: 10, fontWeight: '600', color: '#0F172A' },

  actionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, alignItems: 'center' },
  portBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 8 },
  portBtnText: { fontSize: 10, fontWeight: '700' },
  portedPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  portedText: { fontSize: 10, fontWeight: '700' },
  iconBtn: { width: 26, height: 26, borderRadius: 6, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFFFFF' },

  overlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'flex-end' },
  modal: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxHeight: '92%' },
  modalHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  modalTitle: { flex: 1, fontSize: 16, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 12, fontWeight: '700', color: '#0F172A', marginTop: 10, marginBottom: 4 },
  hint: { fontSize: 11, color: '#64748B', fontWeight: '400' },
  input: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: '#0F172A', backgroundColor: '#FFFFFF' },
  recurRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 },
  modalFoot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 12, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 12 },
  cancelBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: '#F1F5F9' },
  cancelBtnText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#0D9488' },
  saveBtnText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
});
