import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  Modal, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';
import { showAlert } from '../../../../src/utils/alert';

const STATUS_COLOR: Record<string, string> = {
  new: '#3B82F6', auto_routed: '#8B5CF6', routed: '#8B5CF6',
  acknowledged: '#F59E0B', responded: '#6366F1',
  action_pending: '#F97316', action_taken: '#10B981',
  resolution_review: '#06B6D4', closed: '#6B7280', reopened: '#EF4444',
};

const NEXT_ACTION_FROM_STATUS: Record<string, string[]> = {
  new: ['acknowledge'],
  auto_routed: ['acknowledge'],
  routed: ['acknowledge'],
  acknowledged: ['respond', 'action_taken'],
  responded: ['action_taken', 'close'],
  action_pending: ['respond', 'action_taken'],
  action_taken: ['close'],
  resolution_review: ['close'],
  closed: ['reopen'],
  reopened: ['acknowledge'],
};

export default function OrgFeedbackQueue() {
  const router = useRouter();
  const { orgId } = useLocalSearchParams<{ orgId: string }>();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any | null>(null);
  const [action, setAction] = useState<string | null>(null);
  const [responseText, setResponseText] = useState('');
  const [actionDesc, setActionDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

  const load = async () => {
    if (!orgId) return;
    try {
      const url = filter
        ? `/public-pulse/orgs/${orgId}/feedback/queue?status=${filter}`
        : `/public-pulse/orgs/${orgId}/feedback/queue`;
      const res = await api.get(url);
      setItems(res.data.items || []);
    } catch (e) {} finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, [orgId, filter]));

  const openAction = (item: any, act: string) => {
    setSelected(item);
    setAction(act);
    setResponseText('');
    setActionDesc('');
  };

  const submit = async () => {
    if (!selected || !action) return;
    setSubmitting(true);
    try {
      const body: any = { action };
      if (action === 'respond') body.response_text = responseText;
      if (action === 'action_taken') body.action_taken_description = actionDesc;
      await api.post(`/public-pulse/orgs/${orgId}/feedback/${selected.feedback_id}/action`, body);
      setSelected(null); setAction(null);
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  const STATUS_FILTERS = [
    { key: null, label: 'All' },
    { key: 'new', label: 'New' },
    { key: 'auto_routed', label: 'Routed' },
    { key: 'acknowledged', label: 'Acknowledged' },
    { key: 'responded', label: 'Responded' },
    { key: 'action_taken', label: 'Resolved' },
    { key: 'closed', label: 'Closed' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Feedback Queue</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterStrip} contentContainerStyle={{ paddingHorizontal: 16 }}>
        {STATUS_FILTERS.map((f) => {
          const sel = filter === f.key;
          return (
            <TouchableOpacity
              key={f.label}
              style={[styles.filterBtn, sel && styles.filterBtnSel]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[styles.filterTxt, sel && { color: '#FFF' }]}>{f.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : items.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="mail-open" size={32} color="#9CA3AF" />
          <Text style={styles.emptyTxt}>No feedback in this state</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {items.map((it) => {
            const acts = NEXT_ACTION_FROM_STATUS[it.status] || [];
            return (
              <View key={it.feedback_id} style={styles.item}>
                <View style={styles.itemHead}>
                  <View style={[styles.statusPill, { backgroundColor: `${STATUS_COLOR[it.status] || '#6B7280'}20` }]}>
                    <Text style={[styles.statusTxt, { color: STATUS_COLOR[it.status] || '#6B7280' }]}>
                      {it.status?.toUpperCase().replace(/_/g, ' ')}
                    </Text>
                  </View>
                  <Text style={styles.itemDate}>{new Date(it.created_at).toLocaleDateString()}</Text>
                </View>
                <Text style={styles.itemTxt}>{it.feedback_text}</Text>
                {it.district && <Text style={styles.itemMeta}>📍 {it.district} · severity {it.severity}</Text>}
                {it.response_text && (
                  <View style={styles.respBox}><Text style={styles.respLabel}>Response:</Text><Text style={styles.respTxt}>{it.response_text}</Text></View>
                )}
                {it.action_taken_description && (
                  <View style={styles.actBox}><Text style={styles.actLabel}>Action Taken:</Text><Text style={styles.actTxt}>{it.action_taken_description}</Text></View>
                )}
                {acts.length > 0 && (
                  <View style={styles.actionsRow}>
                    {acts.map((a) => (
                      <TouchableOpacity key={a} style={styles.actionBtn} onPress={() => openAction(it, a)}>
                        <Text style={styles.actionBtnTxt}>{a.replace(/_/g, ' ')}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>
            );
          })}
        </ScrollView>
      )}

      {/* Action modal */}
      <Modal visible={!!action} transparent animationType="slide" onRequestClose={() => setAction(null)}>
        <View style={styles.modalBg}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            <View style={styles.modal}>
              <Text style={styles.modalTitle}>{action?.replace(/_/g, ' ').toUpperCase()}</Text>
              <Text style={styles.modalSub}>On: {selected?.feedback_text?.slice(0, 60)}...</Text>
              {action === 'respond' && (
                <TextInput
                  style={styles.modalInput}
                  placeholder="Your response to the citizen..."
                  placeholderTextColor="#9CA3AF"
                  value={responseText}
                  onChangeText={setResponseText}
                  multiline
                />
              )}
              {action === 'action_taken' && (
                <TextInput
                  style={styles.modalInput}
                  placeholder="What action was taken?"
                  placeholderTextColor="#9CA3AF"
                  value={actionDesc}
                  onChangeText={setActionDesc}
                  multiline
                />
              )}
              <View style={styles.modalButtons}>
                <TouchableOpacity style={styles.cancelBtn} onPress={() => { setAction(null); setSelected(null); }}>
                  <Text style={styles.cancelTxt}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.confirmBtn} onPress={submit} disabled={submitting}>
                  {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.confirmTxt}>Confirm</Text>}
                </TouchableOpacity>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  filterStrip: { maxHeight: 50, paddingVertical: 8 },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB', marginRight: 8 },
  filterBtnSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  filterTxt: { fontSize: 12, fontWeight: '600', color: COLORS.text },
  emptyCard: { alignItems: 'center', padding: 40 },
  emptyTxt: { fontSize: 14, color: '#6B7280', marginTop: 8 },
  item: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10 },
  itemHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusTxt: { fontSize: 10, fontWeight: '700' },
  itemDate: { fontSize: 11, color: '#9CA3AF' },
  itemTxt: { fontSize: 13, color: COLORS.text, lineHeight: 19 },
  itemMeta: { fontSize: 11, color: '#6B7280', marginTop: 6 },
  respBox: { backgroundColor: '#EFF6FF', padding: 10, borderRadius: 8, marginTop: 10 },
  respLabel: { fontSize: 11, fontWeight: '700', color: '#1E40AF' },
  respTxt: { fontSize: 12, color: '#1E40AF', marginTop: 2 },
  actBox: { backgroundColor: '#ECFDF5', padding: 10, borderRadius: 8, marginTop: 8 },
  actLabel: { fontSize: 11, fontWeight: '700', color: '#065F46' },
  actTxt: { fontSize: 12, color: '#065F46', marginTop: 2 },
  actionsRow: { flexDirection: 'row', gap: 8, marginTop: 12, flexWrap: 'wrap' },
  actionBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: COLORS.primary },
  actionBtnTxt: { fontSize: 12, color: '#FFF', fontWeight: '600', textTransform: 'capitalize' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modal: { backgroundColor: '#FFF', padding: 20, borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingBottom: 40 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: COLORS.text },
  modalSub: { fontSize: 12, color: '#6B7280', marginTop: 4, marginBottom: 14 },
  modalInput: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, minHeight: 100, textAlignVertical: 'top', fontSize: 14, color: COLORS.text },
  modalButtons: { flexDirection: 'row', gap: 10, marginTop: 16 },
  cancelBtn: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: '#F3F4F6', alignItems: 'center' },
  cancelTxt: { color: COLORS.text, fontWeight: '600' },
  confirmBtn: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: COLORS.primary, alignItems: 'center' },
  confirmTxt: { color: '#FFF', fontWeight: '700' },
});
