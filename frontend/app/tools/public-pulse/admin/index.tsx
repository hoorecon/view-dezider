import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Modal,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';
import { showAlert } from '../../../../src/utils/alert';

export default function AdminModeration() {
  const router = useRouter();
  const [tab, setTab] = useState<'pending' | 'all' | 'audit'>('pending');
  const [apps, setApps] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any | null>(null);
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      if (tab === 'pending') {
        const r = await api.get('/public-pulse/admin/orgs/pending');
        setApps(r.data.applications || []);
      } else if (tab === 'all') {
        const r = await api.get('/public-pulse/admin/orgs/all');
        setApps(r.data.applications || []);
      } else {
        const r = await api.get('/public-pulse/admin/audit-logs?limit=100');
        setLogs(r.data.logs || []);
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, [tab]));

  const review = async () => {
    if (!selected || !decision) return;
    setSubmitting(true);
    try {
      await api.post(
        `/public-pulse/admin/orgs/application/${selected.application_id}/review`,
        { decision, reason: reason || undefined },
      );
      setSelected(null); setDecision(null); setReason('');
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Admin — Public Pulse</Text>
        <View style={{ width: 28 }} />
      </View>

      <View style={styles.tabs}>
        {[
          { key: 'pending', label: 'Pending' },
          { key: 'all', label: 'All Apps' },
          { key: 'audit', label: 'Audit Log' },
        ].map((t) => {
          const sel = tab === t.key;
          return (
            <TouchableOpacity key={t.key} style={[styles.tab, sel && styles.tabSel]} onPress={() => setTab(t.key as any)}>
              <Text style={[styles.tabTxt, sel && { color: '#FFF' }]}>{t.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : tab === 'audit' ? (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {logs.length === 0 ? (
            <Text style={styles.emptyTxt}>No audit entries yet</Text>
          ) : logs.map((l, i) => (
            <View key={i} style={styles.logItem}>
              <Text style={styles.logAction}>{l.action}</Text>
              <Text style={styles.logDate}>{new Date(l.timestamp).toLocaleString()}</Text>
              {l.details && <Text style={styles.logDetails}>{JSON.stringify(l.details).slice(0, 120)}</Text>}
            </View>
          ))}
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {apps.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="checkmark-done-circle" size={32} color="#10B981" />
              <Text style={styles.emptyTxt}>No {tab === 'pending' ? 'pending' : ''} applications</Text>
            </View>
          ) : apps.map((a) => (
            <TouchableOpacity key={a.application_id} style={styles.appCard} onPress={() => setSelected(a)}>
              <View style={{ flex: 1 }}>
                <Text style={styles.appName}>{a.display_name}</Text>
                <Text style={styles.appMeta}>{a.org_type.replace('_', ' ')} · {a.district || 'No district'}</Text>
                <Text style={styles.appMeta}>{a.email} · Submitted {new Date(a.submitted_at).toLocaleDateString()}</Text>
                {a.about && <Text style={styles.appAbout} numberOfLines={2}>{a.about}</Text>}
              </View>
              <View style={[styles.statusPill, { backgroundColor: a.status === 'pending' ? '#FEF3C7' : a.status === 'approved' ? '#D1FAE5' : '#FEE2E2' }]}>
                <Text style={[styles.statusTxt, { color: a.status === 'pending' ? '#92400E' : a.status === 'approved' ? '#065F46' : '#991B1B' }]}>
                  {a.status.toUpperCase()}
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* Review modal */}
      <Modal visible={!!selected && selected.status === 'pending'} transparent animationType="slide" onRequestClose={() => setSelected(null)}>
        <View style={styles.modalBg}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            <View style={styles.modal}>
              <Text style={styles.modalTitle}>Review: {selected?.display_name}</Text>
              <Text style={styles.modalSub}>{selected?.org_type?.replace('_', ' ')} · {selected?.email}</Text>
              {selected?.about && <Text style={styles.aboutTxt}>{selected.about}</Text>}
              {selected?.website && <Text style={styles.websiteTxt}>🌐 {selected.website}</Text>}
              {selected?.categories?.length > 0 && (
                <View style={styles.catRow}>
                  {selected.categories.map((c: string) => (
                    <View key={c} style={styles.catPill}><Text style={styles.catTxt}>{c}</Text></View>
                  ))}
                </View>
              )}

              {selected?.verification_doc_b64 && (
                <Text style={styles.docInfo}>📎 Verification doc attached: {selected.verification_doc_name || 'file'}</Text>
              )}

              {!decision ? (
                <View style={styles.decisionButtons}>
                  <TouchableOpacity style={styles.rejectBtn} onPress={() => setDecision('reject')}>
                    <Ionicons name="close-circle" size={18} color="#FFF" />
                    <Text style={styles.rejectTxt}>Reject</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.approveBtn} onPress={() => setDecision('approve')}>
                    <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                    <Text style={styles.approveTxt}>Approve</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <>
                  {decision === 'reject' && (
                    <TextInput
                      style={styles.reasonInput}
                      placeholder="Reason for rejection (shown to applicant)"
                      placeholderTextColor="#9CA3AF"
                      value={reason}
                      onChangeText={setReason}
                      multiline
                    />
                  )}
                  <View style={styles.decisionButtons}>
                    <TouchableOpacity style={styles.cancelBtn} onPress={() => setDecision(null)}>
                      <Text style={styles.cancelTxt}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.confirmBtn} onPress={review} disabled={submitting}>
                      {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.confirmTxt}>Confirm {decision}</Text>}
                    </TouchableOpacity>
                  </View>
                </>
              )}

              <TouchableOpacity onPress={() => { setSelected(null); setDecision(null); setReason(''); }}>
                <Text style={styles.dismissTxt}>Dismiss</Text>
              </TouchableOpacity>
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
  tabs: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8 },
  tab: { flex: 1, paddingVertical: 10, borderRadius: 10, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center' },
  tabSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  tabTxt: { fontSize: 13, fontWeight: '600', color: COLORS.text },
  emptyCard: { alignItems: 'center', padding: 40 },
  emptyTxt: { fontSize: 14, color: '#6B7280', marginTop: 8, textAlign: 'center' },
  appCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10 },
  appName: { fontSize: 15, fontWeight: '700', color: COLORS.text },
  appMeta: { fontSize: 11, color: '#6B7280', marginTop: 3 },
  appAbout: { fontSize: 12, color: '#374151', marginTop: 6, lineHeight: 17 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusTxt: { fontSize: 10, fontWeight: '700' },
  logItem: { backgroundColor: '#FFF', padding: 12, borderRadius: 10, marginBottom: 8 },
  logAction: { fontSize: 13, fontWeight: '700', color: COLORS.primary },
  logDate: { fontSize: 11, color: '#6B7280', marginTop: 2 },
  logDetails: { fontSize: 11, color: '#374151', marginTop: 4, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modal: { backgroundColor: '#FFF', padding: 20, borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingBottom: 40 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: COLORS.text },
  modalSub: { fontSize: 12, color: '#6B7280', marginTop: 4 },
  aboutTxt: { fontSize: 13, color: '#374151', marginTop: 14, lineHeight: 19 },
  websiteTxt: { fontSize: 12, color: COLORS.primary, marginTop: 8 },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8, gap: 6 },
  catPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: '#EEF2FF' },
  catTxt: { fontSize: 11, color: COLORS.primary, fontWeight: '600' },
  docInfo: { fontSize: 12, color: '#6B7280', marginTop: 12, fontStyle: 'italic' },
  decisionButtons: { flexDirection: 'row', gap: 10, marginTop: 16 },
  rejectBtn: { flex: 1, flexDirection: 'row', padding: 14, borderRadius: 10, backgroundColor: '#EF4444', alignItems: 'center', justifyContent: 'center', gap: 6 },
  rejectTxt: { color: '#FFF', fontWeight: '700' },
  approveBtn: { flex: 1, flexDirection: 'row', padding: 14, borderRadius: 10, backgroundColor: '#10B981', alignItems: 'center', justifyContent: 'center', gap: 6 },
  approveTxt: { color: '#FFF', fontWeight: '700' },
  reasonInput: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, marginTop: 16, minHeight: 80, textAlignVertical: 'top', fontSize: 14, color: COLORS.text },
  cancelBtn: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: '#F3F4F6', alignItems: 'center' },
  cancelTxt: { color: COLORS.text, fontWeight: '600' },
  confirmBtn: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: COLORS.primary, alignItems: 'center' },
  confirmTxt: { color: '#FFF', fontWeight: '700' },
  dismissTxt: { textAlign: 'center', color: '#6B7280', marginTop: 14, fontSize: 13 },
});
