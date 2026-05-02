import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput, Modal, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const SEVERITY_COLORS: Record<string, {bg: string; text: string; icon: string}> = {
  critical: { bg: '#FEF2F2', text: '#DC2626', icon: 'alert-circle' },
  high: { bg: '#FFF7ED', text: '#EA580C', icon: 'warning' },
  medium: { bg: '#FFFBEB', text: '#D97706', icon: 'information-circle' },
  low: { bg: '#F0FDF4', text: '#16A34A', icon: 'checkmark-circle' },
};

const STATUS_LABELS: Record<string, {label: string; color: string}> = {
  detected: { label: 'Detected', color: '#DC2626' },
  investigating: { label: 'Investigating', color: '#EA580C' },
  contained: { label: 'Contained', color: '#D97706' },
  certin_notified: { label: 'CERT-In Notified', color: '#2563EB' },
  users_notified: { label: 'Users Notified', color: '#7C3AED' },
  resolved: { label: 'Resolved', color: '#059669' },
  post_mortem: { label: 'Post Mortem', color: '#6B7280' },
};

export default function IncidentResponseScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState<any>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportText, setReportText] = useState('');
  const [notifying, setNotifying] = useState('');
  const [auditStats, setAuditStats] = useState<any>(null);

  const [form, setForm] = useState({
    title: '', incident_type: 'data_breach', severity: 'high',
    description: '', affected_systems: '', affected_user_count: '0',
    kyc_data_involved: false, initial_actions_taken: '',
  });

  const fetchData = async () => {
    try {
      const [incRes, statsRes] = await Promise.all([
        api.get('/incidents'),
        api.get('/audit-trail/stats').catch(() => ({ data: null })),
      ]);
      setIncidents(incRes.data || []);
      setAuditStats(statsRes.data);
    } catch (err: any) {
      if (err.response?.status !== 403) showAlert('Error', err.response?.data?.detail || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const handleCreate = async () => {
    if (!form.title || !form.description) {
      showAlert('Required', 'Title and Description are required'); return;
    }
    if (form.description.length < 50) {
      showAlert('Required', 'Description must be at least 50 characters'); return;
    }
    setCreating(true);
    try {
      await api.post('/incidents', {
        ...form,
        affected_systems: form.affected_systems.split(',').map(s => s.trim()).filter(Boolean),
        affected_user_count: parseInt(form.affected_user_count) || 0,
      });
      showAlert('Incident Logged', 'Security incident has been recorded. Proceed to notify CERT-In within 6 hours.');
      setShowCreate(false);
      setForm({ title: '', incident_type: 'data_breach', severity: 'high', description: '', affected_systems: '', affected_user_count: '0', kyc_data_involved: false, initial_actions_taken: '' });
      fetchData();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to create incident');
    } finally {
      setCreating(false);
    }
  };

  const handleNotifyCertIn = async (incId: string) => {
    setNotifying('certin_' + incId);
    try {
      const res = await api.post(`/incidents/${incId}/notify-certin`);
      showAlert('CERT-In Report', res.data?.email_sent
        ? 'Report emailed to CERT-In successfully!'
        : 'Report generated and stored. Configure SMTP to auto-email to incident@cert-in.org.in');
      fetchData();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed');
    } finally {
      setNotifying('');
    }
  };

  const handleNotifyUsers = async (incId: string) => {
    setNotifying('users_' + incId);
    try {
      const res = await api.post(`/incidents/${incId}/notify-users`, {
        scope: 'all',
      });
      showAlert('Users Notified', `Sent to ${res.data?.total_users} users. WhatsApp: ${res.data?.whatsapp_sent}, In-app: ${res.data?.inapp_notifications}`);
      fetchData();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed');
    } finally {
      setNotifying('');
    }
  };

  const viewReport = async (incId: string) => {
    try {
      const res = await api.get(`/incidents/${incId}/report`);
      setReportText(res.data?.report || '');
      setShowReport(true);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed');
    }
  };

  const updateStatus = async (incId: string, status: string) => {
    try {
      await api.put(`/incidents/${incId}`, { status });
      fetchData();
      if (selectedIncident?.id === incId) {
        setSelectedIncident({ ...selectedIncident, status });
      }
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed');
    }
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#DC2626" /></View>;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#DC2626', '#991B1B']} style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Incident Response</Text>
          <Text style={styles.headerSub}>CERT-In Compliant • DPDPA 2023</Text>
        </View>
        <TouchableOpacity style={styles.auditBtn} onPress={() => router.push('/admin/audit-trail')}>
          <Ionicons name="eye" size={16} color="#DC2626" />
        </TouchableOpacity>
      </LinearGradient>

      <ScrollView style={styles.body} refreshControl={<RefreshControl refreshing={false} onRefresh={fetchData} />}>
        {/* Audit Stats Banner */}
        {auditStats && (
          <View style={styles.statsBanner}>
            <View style={styles.statItem}>
              <Text style={styles.statNum}>{auditStats.total_events}</Text>
              <Text style={styles.statLabel}>Audit Events</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={[styles.statNum, { color: '#DC2626' }]}>{auditStats.sensitive_accesses}</Text>
              <Text style={styles.statLabel}>Sensitive</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={[styles.statNum, { color: '#7C3AED' }]}>{auditStats.kyc_related}</Text>
              <Text style={styles.statLabel}>KYC Events</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={[styles.statNum, { color: '#F97316' }]}>{auditStats.last_24h}</Text>
              <Text style={styles.statLabel}>Last 24h</Text>
            </View>
          </View>
        )}

        {/* Create Button */}
        <TouchableOpacity style={styles.createBtn} onPress={() => setShowCreate(true)}>
          <Ionicons name="add-circle" size={20} color="#FFF" />
          <Text style={styles.createBtnText}>Log New Incident</Text>
        </TouchableOpacity>

        {/* Incidents List */}
        {incidents.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="shield-checkmark" size={48} color="#D1D5DB" />
            <Text style={styles.emptyTitle}>No Incidents Reported</Text>
            <Text style={styles.emptyDesc}>All systems operating normally</Text>
          </View>
        ) : (
          incidents.map((inc: any) => {
            const sev = SEVERITY_COLORS[inc.severity] || SEVERITY_COLORS.medium;
            const st = STATUS_LABELS[inc.status] || { label: inc.status, color: '#6B7280' };
            return (
              <View key={inc.id} style={[styles.incCard, { borderLeftColor: sev.text }]}>
                <View style={styles.incHeader}>
                  <View style={[styles.sevBadge, { backgroundColor: sev.bg }]}>
                    <Ionicons name={sev.icon as any} size={14} color={sev.text} />
                    <Text style={[styles.sevText, { color: sev.text }]}>{inc.severity?.toUpperCase()}</Text>
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: st.color + '15' }]}>
                    <Text style={[styles.statusText, { color: st.color }]}>{st.label}</Text>
                  </View>
                  <Text style={styles.incId}>{inc.id}</Text>
                </View>

                <Text style={styles.incTitle}>{inc.title}</Text>
                <Text style={styles.incDesc} numberOfLines={2}>{inc.description}</Text>

                <View style={styles.incMeta}>
                  {inc.kyc_data_involved && (
                    <View style={styles.kycBadge}>
                      <Ionicons name="finger-print" size={10} color="#DC2626" />
                      <Text style={styles.kycBadgeText}>KYC Data</Text>
                    </View>
                  )}
                  <Text style={styles.incDate}>{new Date(inc.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</Text>
                  <Text style={styles.incUsers}>{inc.affected_user_count} users affected</Text>
                </View>

                {/* Action Buttons */}
                <View style={styles.incActions}>
                  {!inc.certin_notified && (
                    <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#DC2626' }]}
                      onPress={() => handleNotifyCertIn(inc.id)} disabled={notifying === 'certin_' + inc.id}>
                      {notifying === 'certin_' + inc.id ? <ActivityIndicator color="#FFF" size="small" /> : (
                        <><Ionicons name="megaphone" size={12} color="#FFF" /><Text style={styles.actionText}>CERT-In</Text></>
                      )}
                    </TouchableOpacity>
                  )}
                  {inc.certin_notified && !inc.users_notified && (
                    <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#7C3AED' }]}
                      onPress={() => handleNotifyUsers(inc.id)} disabled={notifying === 'users_' + inc.id}>
                      {notifying === 'users_' + inc.id ? <ActivityIndicator color="#FFF" size="small" /> : (
                        <><Ionicons name="people" size={12} color="#FFF" /><Text style={styles.actionText}>Notify Users</Text></>
                      )}
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#374151' }]}
                    onPress={() => viewReport(inc.id)}>
                    <Ionicons name="document-text" size={12} color="#FFF" />
                    <Text style={styles.actionText}>Report</Text>
                  </TouchableOpacity>
                  {inc.status !== 'resolved' && (
                    <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#059669' }]}
                      onPress={() => updateStatus(inc.id, 'resolved')}>
                      <Ionicons name="checkmark" size={12} color="#FFF" />
                      <Text style={styles.actionText}>Resolve</Text>
                    </TouchableOpacity>
                  )}
                </View>

                {/* SLA Indicators */}
                {inc.certin_notified && (
                  <View style={styles.slaRow}>
                    <Ionicons name="checkmark-circle" size={12} color="#059669" />
                    <Text style={styles.slaText}>CERT-In notified {inc.certin_notified_at ? new Date(inc.certin_notified_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}</Text>
                  </View>
                )}
                {inc.users_notified && (
                  <View style={styles.slaRow}>
                    <Ionicons name="checkmark-circle" size={12} color="#7C3AED" />
                    <Text style={styles.slaText}>{inc.users_notified_count} users notified {inc.users_notified_at ? new Date(inc.users_notified_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}</Text>
                  </View>
                )}
              </View>
            );
          })
        )}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Create Incident Modal */}
      <Modal visible={showCreate} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons name="warning" size={22} color="#DC2626" />
              <Text style={styles.modalTitle}>Log Security Incident</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 450 }} showsVerticalScrollIndicator={false}>
              <Text style={styles.fieldLabel}>Title *</Text>
              <TextInput style={styles.input} placeholder="Brief incident title" value={form.title}
                onChangeText={v => setForm({ ...form, title: v })} />

              <Text style={styles.fieldLabel}>Severity</Text>
              <View style={styles.chipRow}>
                {['critical', 'high', 'medium', 'low'].map(s => (
                  <TouchableOpacity key={s} style={[styles.chip, form.severity === s && { backgroundColor: SEVERITY_COLORS[s].text }]}
                    onPress={() => setForm({ ...form, severity: s })}>
                    <Text style={[styles.chipText, form.severity === s && { color: '#FFF' }]}>{s.toUpperCase()}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.fieldLabel}>Type</Text>
              <View style={styles.chipRow}>
                {['data_breach', 'unauthorized_access', 'kyc_data_exposure', 'phishing', 'other'].map(t => (
                  <TouchableOpacity key={t} style={[styles.chip, form.incident_type === t && styles.chipActive]}
                    onPress={() => setForm({ ...form, incident_type: t })}>
                    <Text style={[styles.chipText, form.incident_type === t && { color: '#FFF' }]}>{t.replace(/_/g, ' ')}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.fieldLabel}>Description * (min 50 chars)</Text>
              <TextInput style={[styles.input, { height: 80 }]} multiline placeholder="Detailed description of the incident..."
                value={form.description} onChangeText={v => setForm({ ...form, description: v })} />

              <Text style={styles.fieldLabel}>Affected Systems (comma-separated)</Text>
              <TextInput style={styles.input} placeholder="e.g. MongoDB, DigiLocker API, User Auth"
                value={form.affected_systems} onChangeText={v => setForm({ ...form, affected_systems: v })} />

              <Text style={styles.fieldLabel}>Estimated Affected Users</Text>
              <TextInput style={styles.input} placeholder="0" keyboardType="numeric"
                value={form.affected_user_count} onChangeText={v => setForm({ ...form, affected_user_count: v })} />

              <TouchableOpacity style={styles.kycToggle}
                onPress={() => setForm({ ...form, kyc_data_involved: !form.kyc_data_involved })}>
                <Ionicons name={form.kyc_data_involved ? 'checkbox' : 'square-outline'} size={20}
                  color={form.kyc_data_involved ? '#DC2626' : '#9CA3AF'} />
                <Text style={styles.kycToggleText}>KYC / Aadhaar Data Involved</Text>
              </TouchableOpacity>

              <Text style={styles.fieldLabel}>Initial Actions Taken</Text>
              <TextInput style={[styles.input, { height: 60 }]} multiline placeholder="Steps already taken to contain..."
                value={form.initial_actions_taken} onChangeText={v => setForm({ ...form, initial_actions_taken: v })} />
            </ScrollView>

            <TouchableOpacity style={styles.submitBtn} onPress={handleCreate} disabled={creating}>
              {creating ? <ActivityIndicator color="#FFF" size="small" /> : (
                <><Ionicons name="alert-circle" size={16} color="#FFF" /><Text style={styles.submitBtnText}>Log Incident</Text></>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Report Preview Modal */}
      <Modal visible={showReport} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { maxHeight: '80%' }]}>
            <View style={styles.modalHeader}>
              <Ionicons name="document-text" size={22} color="#374151" />
              <Text style={styles.modalTitle}>CERT-In Report</Text>
              <TouchableOpacity onPress={() => setShowReport(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 500 }}>
              <Text style={styles.reportText}>{reportText}</Text>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  auditBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center' },
  body: { flex: 1, padding: 16 },

  statsBanner: { flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 16, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  statItem: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '800', color: '#1F2937' },
  statLabel: { fontSize: 10, color: '#9CA3AF', marginTop: 2 },
  statDivider: { width: 1, backgroundColor: '#F3F4F6', marginHorizontal: 4 },

  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#DC2626', borderRadius: 12, padding: 14, marginBottom: 16 },
  createBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  emptyState: { alignItems: 'center', paddingVertical: 60, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#374151' },
  emptyDesc: { fontSize: 12, color: '#9CA3AF' },

  incCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 12, borderLeftWidth: 4, shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 6, elevation: 1 },
  incHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  sevBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  sevText: { fontSize: 10, fontWeight: '700' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusText: { fontSize: 10, fontWeight: '600' },
  incId: { fontSize: 10, color: '#9CA3AF', marginLeft: 'auto' },
  incTitle: { fontSize: 15, fontWeight: '700', color: '#1F2937', marginBottom: 4 },
  incDesc: { fontSize: 12, color: '#6B7280', lineHeight: 18, marginBottom: 8 },
  incMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  kycBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#FEF2F2', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  kycBadgeText: { fontSize: 9, fontWeight: '600', color: '#DC2626' },
  incDate: { fontSize: 10, color: '#9CA3AF' },
  incUsers: { fontSize: 10, color: '#9CA3AF' },
  incActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6 },
  actionText: { fontSize: 11, fontWeight: '600', color: '#FFF' },
  slaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  slaText: { fontSize: 10, color: '#6B7280' },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { width: '100%', maxWidth: 500, backgroundColor: '#FFF', borderRadius: 20, padding: 20, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 },
  modalTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: '#1F2937' },

  fieldLabel: { fontSize: 12, fontWeight: '600', color: '#374151', marginBottom: 4, marginTop: 10 },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, fontSize: 14, color: '#1F2937', backgroundColor: '#F9FAFB' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 4 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB' },
  chipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  chipText: { fontSize: 11, fontWeight: '600', color: '#6B7280' },
  kycToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, padding: 10, backgroundColor: '#FEF2F2', borderRadius: 8 },
  kycToggleText: { fontSize: 13, fontWeight: '600', color: '#DC2626' },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#DC2626', borderRadius: 12, padding: 14, marginTop: 16 },
  submitBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  reportText: { fontSize: 12, color: '#374151', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', lineHeight: 18 },
});
