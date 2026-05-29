/**
 * /admin/expert-review-queue — L4 Expert Review fulfillment workflow.
 *
 * Admin-only queue of paid Expert Reviews waiting for human action.
 * Workflow:
 *   awaiting_assignment → admin assigns an expert (status → in_progress)
 *   in_progress         → admin marks delivered (with deliverable URL/note)
 *   delivered/cancelled → archival
 *
 * Data: GET /api/store/admin/l4-queue, POST /assign, PUT /status.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Modal, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert, confirmDialog } from '../../src/utils/alert';

interface Delivery {
  id: string;
  user_id: string;
  user_name?: string;
  user_email?: string;
  module?: string;
  decision_id?: string;
  status: string;
  expert_id?: string;
  expert_name?: string;
  assigned_at?: string;
  due_at?: string;
  delivered_at?: string;
  deliverable_url?: string;
  deliverable_note?: string;
  admin_notes?: string;
  created_at?: string;
  order_id?: string;
}

interface ExpertOpt { expert_id: string; name: string; specializations?: string[]; rating_avg?: number; is_online?: boolean; }

const STATUS_META: Record<string, { color: string; bg: string; label: string; icon: any }> = {
  awaiting_assignment: { color: '#B45309', bg: '#FEF3C7', label: 'Awaiting', icon: 'time' },
  in_progress:         { color: '#1D4ED8', bg: '#DBEAFE', label: 'In progress', icon: 'sync' },
  delivered:           { color: '#15803D', bg: '#DCFCE7', label: 'Delivered', icon: 'checkmark-circle' },
  cancelled:           { color: '#9CA3AF', bg: '#F3F4F6', label: 'Cancelled', icon: 'close-circle' },
};

const MODULE_LABEL: Record<string, string> = {
  dezider: 'My Dezider',
  pros_cons: 'Pros & Cons',
  swot: 'SWOT',
};

export default function AdminL4Queue() {
  const [items, setItems] = useState<Delivery[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);
  const [assigning, setAssigning] = useState<Delivery | null>(null);
  const [delivering, setDelivering] = useState<Delivery | null>(null);
  const [experts, setExperts] = useState<ExpertOpt[]>([]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/store/admin/l4-queue', { params: filter ? { status: filter } : {} });
      setItems(r.data.items || []);
      setCounts(r.data.counts || {});
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not fetch queue');
    } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api.get('/store/admin/experts-pick-list')
      .then(r => setExperts(r.data?.experts || []))
      .catch(() => setExperts([]));
  }, []);

  const refreshAfter = async () => { await load(); };

  const cancelDelivery = useCallback(async (d: Delivery) => {
    const ok = await confirmDialog('Cancel this review?', `Refund handling is manual — admin should refund via Razorpay dashboard.`, { confirmText: 'Cancel review', destructive: true });
    if (!ok) return;
    try {
      await api.put(`/store/admin/l4-queue/${d.id}/status`, { status: 'cancelled' });
      await refreshAfter();
      showAlert('Cancelled', 'Delivery marked cancelled.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not cancel');
    }
  }, []);

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#7C3AED" /></View>;

  return (
    <ScrollView contentContainerStyle={s.body}>
      <Text style={s.h1}>Expert Review Queue · L4</Text>
      <Text style={s.sub}>Paid Expert Reviews waiting for fulfillment. Default SLA: 48 hours.</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filterRow}>
        <FilterChip label={`All · ${items.length}`} active={!filter} onPress={() => setFilter(null)} tone="#475569" />
        {Object.entries(STATUS_META).map(([k, m]) => (
          <FilterChip
            key={k}
            label={`${m.label} · ${counts[k] ?? 0}`}
            active={filter === k}
            onPress={() => setFilter(filter === k ? null : k)}
            tone={m.color}
          />
        ))}
      </ScrollView>

      {items.length === 0 ? (
        <View style={s.empty}>
          <Ionicons name="cafe-outline" size={48} color="#CBD5E1" />
          <Text style={s.emptyText}>Nothing in this bucket. Sip a coffee. ☕</Text>
        </View>
      ) : items.map(d => {
        const meta = STATUS_META[d.status] || STATUS_META.awaiting_assignment;
        return (
          <View key={d.id} style={s.card}>
            <View style={s.cardHead}>
              <View style={[s.statusChip, { backgroundColor: meta.bg }]}>
                <Ionicons name={meta.icon} size={12} color={meta.color} />
                <Text style={[s.statusText, { color: meta.color }]}>{meta.label}</Text>
              </View>
              <View style={{ flex: 1 }} />
              <Text style={s.metaText}>{new Date(d.created_at || '').toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</Text>
            </View>

            <Text style={s.user}>
              {d.user_name || d.user_id || 'Unknown user'}
              {d.user_email ? <Text style={s.userEmail}> · {d.user_email}</Text> : null}
            </Text>

            <View style={s.metaRow}>
              <MetaPill icon="layers" label={MODULE_LABEL[d.module || ''] || d.module || '—'} />
              {d.decision_id ? <MetaPill icon="link" label={`Decision ${d.decision_id.slice(0, 8)}…`} /> : null}
              {d.order_id ? <MetaPill icon="card" label={`Order ${d.order_id.slice(-8)}`} /> : null}
            </View>

            {d.expert_name ? (
              <View style={s.expertRow}>
                <Ionicons name="person-circle" size={16} color="#7C3AED" />
                <Text style={s.expertText}>Assigned to <Text style={{ fontWeight: '700' }}>{d.expert_name}</Text>{d.due_at ? <Text style={s.metaText}> · due {new Date(d.due_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</Text> : null}</Text>
              </View>
            ) : null}

            {d.admin_notes ? <Text style={s.notes}>📝 {d.admin_notes}</Text> : null}
            {d.deliverable_url ? <Text style={s.notes}>📎 {d.deliverable_url}</Text> : null}
            {d.deliverable_note ? <Text style={s.notes}>✅ {d.deliverable_note}</Text> : null}

            <View style={s.actionsRow}>
              {d.status === 'awaiting_assignment' && (
                <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={() => setAssigning(d)}>
                  <Ionicons name="person-add" size={14} color="#FFF" />
                  <Text style={s.btnPrimaryText}>Assign expert</Text>
                </TouchableOpacity>
              )}
              {d.status === 'in_progress' && (
                <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={() => setDelivering(d)}>
                  <Ionicons name="cloud-upload" size={14} color="#FFF" />
                  <Text style={s.btnPrimaryText}>Mark delivered</Text>
                </TouchableOpacity>
              )}
              {(d.status === 'awaiting_assignment' || d.status === 'in_progress') && (
                <TouchableOpacity style={[s.btn, s.btnGhost]} onPress={() => cancelDelivery(d)}>
                  <Ionicons name="close" size={14} color="#DC2626" />
                  <Text style={s.btnGhostText}>Cancel</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        );
      })}

      {/* Assign Modal */}
      {assigning && <AssignModal d={assigning} experts={experts} onClose={() => setAssigning(null)} onDone={async () => { setAssigning(null); await refreshAfter(); }} />}
      {/* Deliver Modal */}
      {delivering && <DeliverModal d={delivering} onClose={() => setDelivering(null)} onDone={async () => { setDelivering(null); await refreshAfter(); }} />}
    </ScrollView>
  );
}

function FilterChip({ label, active, onPress, tone }: { label: string; active: boolean; onPress: () => void; tone: string }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.filterChip, active && { backgroundColor: tone + '22', borderColor: tone }]}>
      <Text style={[s.filterChipText, active && { color: tone, fontWeight: '700' }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function MetaPill({ icon, label }: { icon: any; label: string }) {
  return (
    <View style={s.metaPill}>
      <Ionicons name={icon} size={11} color="#64748B" />
      <Text style={s.metaPillText}>{label}</Text>
    </View>
  );
}

function AssignModal({ d, experts, onClose, onDone }: { d: Delivery; experts: ExpertOpt[]; onClose: () => void; onDone: () => void }) {
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [slaHrs, setSlaHrs] = useState('48');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const ranked = useMemo(() => {
    const moduleKey = (d.module || '').toLowerCase();
    // Simple heuristic: experts with specializations matching module slug rank first
    return [...experts].sort((a, b) => {
      const aMatch = (a.specializations || []).some(sp => sp.toLowerCase().includes(moduleKey)) ? 1 : 0;
      const bMatch = (b.specializations || []).some(sp => sp.toLowerCase().includes(moduleKey)) ? 1 : 0;
      if (aMatch !== bMatch) return bMatch - aMatch;
      return (b.rating_avg || 0) - (a.rating_avg || 0);
    });
  }, [d.module, experts]);

  const submit = async () => {
    if (!pickedId) return showAlert('Pick an expert', 'Select someone from the list first.');
    setSubmitting(true);
    try {
      await api.post(`/store/admin/l4-queue/${d.id}/assign`, {
        expert_id: pickedId,
        sla_hours: parseInt(slaHrs, 10) || 48,
        admin_notes: notes || undefined,
      });
      showAlert('Assigned', `Expert assigned. SLA ${slaHrs}h.`);
      onDone();
    } catch (e: any) {
      showAlert('Assign failed', e?.response?.data?.detail || 'Error');
    } finally { setSubmitting(false); }
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.modalBg}>
        <View style={s.modalCard}>
          <View style={s.modalHead}>
            <Text style={s.modalTitle}>Assign Expert</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={20} color="#475569" /></TouchableOpacity>
          </View>
          <Text style={s.modalSub}>For {d.user_name || d.user_email || d.user_id} · Module {MODULE_LABEL[d.module || ''] || d.module}</Text>

          <Text style={s.label}>Expert</Text>
          <ScrollView style={s.expertList} nestedScrollEnabled>
            {ranked.map(e => (
              <TouchableOpacity key={e.expert_id} style={[s.expertRowItem, pickedId === e.expert_id && s.expertRowItemActive]} onPress={() => setPickedId(e.expert_id)}>
                <Ionicons name={pickedId === e.expert_id ? 'radio-button-on' : 'radio-button-off'} size={16} color={pickedId === e.expert_id ? '#7C3AED' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={s.expertName}>{e.name} {e.is_online ? <Text style={{ color: '#16A34A', fontSize: 11 }}>● online</Text> : null}</Text>
                  <Text style={s.expertSpec} numberOfLines={1}>{(e.specializations || []).join(' · ') || 'No specializations listed'}</Text>
                </View>
                {e.rating_avg ? <Text style={s.expertRating}>★ {e.rating_avg.toFixed(1)}</Text> : null}
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={s.row2}>
            <View style={{ flex: 1 }}>
              <Text style={s.label}>SLA (hours)</Text>
              <TextInput value={slaHrs} onChangeText={setSlaHrs} keyboardType="numeric" style={s.input} />
            </View>
          </View>
          <Text style={s.label}>Notes for expert (optional)</Text>
          <TextInput value={notes} onChangeText={setNotes} multiline style={[s.input, { minHeight: 60, textAlignVertical: 'top' }]} placeholder="Context for the expert..." />

          <View style={s.modalFooter}>
            <TouchableOpacity onPress={onClose} style={[s.btn, s.btnGhost]}><Text style={s.btnGhostText}>Close</Text></TouchableOpacity>
            <TouchableOpacity onPress={submit} disabled={submitting} style={[s.btn, s.btnPrimary, submitting && { opacity: 0.6 }]}>
              {submitting ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.btnPrimaryText}>Assign</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function DeliverModal({ d, onClose, onDone }: { d: Delivery; onClose: () => void; onDone: () => void }) {
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.put(`/store/admin/l4-queue/${d.id}/status`, {
        status: 'delivered',
        deliverable_url: url || undefined,
        deliverable_note: note || undefined,
      });
      showAlert('Delivered', 'Marked as delivered. The user will see this in their account.');
      onDone();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not mark delivered');
    } finally { setSubmitting(false); }
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.modalBg}>
        <View style={s.modalCard}>
          <View style={s.modalHead}>
            <Text style={s.modalTitle}>Mark Delivered</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={20} color="#475569" /></TouchableOpacity>
          </View>
          <Text style={s.modalSub}>Provide the deliverable link or short summary.</Text>

          <Text style={s.label}>Deliverable URL (Google Doc, PDF link, etc.)</Text>
          <TextInput value={url} onChangeText={setUrl} placeholder="https://..." autoCapitalize="none" style={s.input} />

          <Text style={s.label}>Note to user (optional)</Text>
          <TextInput value={note} onChangeText={setNote} multiline style={[s.input, { minHeight: 70, textAlignVertical: 'top' }]} placeholder="Summary of findings & recommendations..." />

          <View style={s.modalFooter}>
            <TouchableOpacity onPress={onClose} style={[s.btn, s.btnGhost]}><Text style={s.btnGhostText}>Close</Text></TouchableOpacity>
            <TouchableOpacity onPress={submit} disabled={submitting} style={[s.btn, s.btnPrimary, submitting && { opacity: 0.6 }]}>
              {submitting ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.btnPrimaryText}>Save & deliver</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  body: { padding: 18, gap: 12, paddingBottom: 60 },
  h1: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 13, color: '#64748B', marginTop: 2, marginBottom: 8 },
  filterRow: { gap: 8, paddingVertical: 6 },
  filterChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#F8FAFC' },
  filterChipText: { fontSize: 12, color: '#475569', fontWeight: '600' },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: 50, gap: 10 },
  emptyText: { color: '#94A3B8', fontSize: 13 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E5E7EB' },
  cardHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  statusChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 3, borderRadius: 999 },
  statusText: { fontSize: 11, fontWeight: '700' },
  metaText: { fontSize: 11, color: '#94A3B8' },
  user: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  userEmail: { fontWeight: '500', color: '#64748B', fontSize: 12 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  metaPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, backgroundColor: '#F1F5F9', borderRadius: 6 },
  metaPillText: { fontSize: 11, color: '#475569', fontWeight: '500' },
  expertRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  expertText: { color: '#475569', fontSize: 13 },
  notes: { fontSize: 12, color: '#475569', backgroundColor: '#F8FAFC', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6, marginTop: 6 },
  actionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  btnPrimary: { backgroundColor: '#7C3AED' },
  btnPrimaryText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  btnGhost: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' },
  btnGhostText: { color: '#DC2626', fontWeight: '700', fontSize: 13 },
  // modal
  modalBg: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  modalCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, maxWidth: 520, width: '100%', gap: 6, maxHeight: '90%' },
  modalHead: { flexDirection: 'row', alignItems: 'center' },
  modalTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#0F172A' },
  modalSub: { fontSize: 12, color: '#64748B', marginBottom: 8 },
  modalFooter: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 14 },
  label: { fontSize: 11, color: '#475569', fontWeight: '700', marginTop: 10, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: Platform.OS === 'web' ? 10 : 8, fontSize: 14, backgroundColor: '#F8FAFC', color: '#0F172A' },
  row2: { flexDirection: 'row', gap: 12 },
  expertList: { maxHeight: 240, marginTop: 4 },
  expertRowItem: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingHorizontal: 8, borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 8, marginBottom: 6 },
  expertRowItemActive: { borderColor: '#7C3AED', backgroundColor: '#F5F3FF' },
  expertName: { fontSize: 13, fontWeight: '600', color: '#0F172A' },
  expertSpec: { fontSize: 11, color: '#64748B', marginTop: 2 },
  expertRating: { fontSize: 12, color: '#B45309', fontWeight: '700' },
});
