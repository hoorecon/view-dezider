/**
 * Privacy & Data (DPDP Act 2023 compliance)
 * - Export my data   → GET  /api/dpdp/export
 * - Delete account   → POST /api/dpdp/delete-request
 * - Cancel deletion  → POST /api/dpdp/cancel-delete
 * - Deletion status  → GET  /api/dpdp/status
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  Platform,
  Share,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { showAlert } from '../../src/utils/alert';

interface DpdpStatus {
  deletion_status?: string;            // "none" | "pending" | "cancelled"
  deletion_requested_at?: string | null;
  deletion_grace_until?: string | null;
}

export default function PrivacyDataScreen() {
  const router = useRouter();
  const [status, setStatus] = useState<DpdpStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmPhrase, setConfirmPhrase] = useState('');
  const [reason, setReason] = useState('');
  const [showDeleteForm, setShowDeleteForm] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      setLoadingStatus(true);
      const res = await api.get('/dpdp/status');
      setStatus(res.data);
    } catch (e: any) {
      console.error('DPDP status error:', e?.response?.data || e.message);
      setStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleExport = async () => {
    try {
      setExporting(true);
      const res = await api.get('/dpdp/export');
      const payload = JSON.stringify(res.data, null, 2);

      if (Platform.OS === 'web') {
        try {
          await Clipboard.setStringAsync(payload);
          showAlert('Export ready', 'Your data JSON has been copied to the clipboard. Paste into a .json file to save.');
        } catch {
          showAlert('Export ready', `Data exported (${payload.length.toLocaleString()} chars). Open console to view.`);
          console.log('[DPDP export]', payload);
        }
      } else {
        try {
          await Share.share({
            title: 'My View Dezider Data Export',
            message: payload,
          });
        } catch (e) {
          await Clipboard.setStringAsync(payload);
          showAlert('Export copied', 'Unable to share directly — payload copied to clipboard.');
        }
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Export failed';
      showAlert('Export failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setExporting(false);
    }
  };

  const handleRequestDeletion = async () => {
    if (confirmPhrase.trim().toUpperCase() !== 'DELETE MY ACCOUNT') {
      showAlert('Confirmation required', 'Type "DELETE MY ACCOUNT" exactly to confirm.');
      return;
    }
    showAlert(
      'Delete Account?',
      'Your account will be scheduled for deletion. You have a 30-day cooling-off period to cancel before data is permanently purged.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          style: 'destructive',
          onPress: async () => {
            try {
              setDeleting(true);
              await api.post('/dpdp/delete-request', {
                confirmation: confirmPhrase.trim(),
                reason: reason.trim() || null,
              });
              showAlert('Deletion scheduled', 'Your account is now pending deletion. You can cancel anytime within the cooling-off period.');
              setConfirmPhrase('');
              setReason('');
              setShowDeleteForm(false);
              fetchStatus();
            } catch (e: any) {
              const msg = e?.response?.data?.detail || e.message || 'Request failed';
              showAlert('Deletion request failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  };

  const handleCancelDeletion = async () => {
    showAlert(
      'Cancel deletion?',
      'This will reverse your pending deletion request. Your account will remain active.',
      [
        { text: 'Keep pending', style: 'cancel' },
        {
          text: 'Cancel deletion',
          onPress: async () => {
            try {
              setCancelling(true);
              await api.post('/dpdp/cancel-delete', {});
              showAlert('Deletion cancelled', 'Your account has been restored.');
              fetchStatus();
            } catch (e: any) {
              const msg = e?.response?.data?.detail || e.message || 'Cancel failed';
              showAlert('Cancel failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
            } finally {
              setCancelling(false);
            }
          },
        },
      ]
    );
  };

  const formatDate = (iso?: string | null) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
    } catch {
      return iso;
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Privacy & Data</Text>
        <View style={{ width: 22 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Intro */}
        <Card style={styles.introCard}>
          <View style={styles.introRow}>
            <Ionicons name="shield-checkmark" size={24} color={COLORS.success} />
            <Text style={styles.introTitle}>DPDP Act 2023 rights</Text>
          </View>
          <Text style={styles.introText}>
            You have the right to access your personal data, request deletion, and withdraw consent. Deletion
            has a cooling-off window so you can change your mind.
          </Text>
        </Card>

        {/* Status */}
        <Card style={styles.card}>
          <Text style={styles.cardTitle}>Deletion status</Text>
          {loadingStatus ? (
            <ActivityIndicator size="small" color={COLORS.primary} style={{ marginTop: 12 }} />
          ) : (status?.deletion_status === 'pending') ? (
            <View style={styles.pendingBox}>
              <View style={styles.pendingRow}>
                <Ionicons name="warning" size={18} color="#B45309" />
                <Text style={styles.pendingTitle}>Deletion pending</Text>
              </View>
              <Text style={styles.pendingLine}>Requested: {formatDate(status.deletion_requested_at)}</Text>
              <Text style={styles.pendingLine}>Scheduled purge: {formatDate(status.deletion_grace_until)}</Text>
              {status.reason ? <Text style={styles.pendingLine}>Reason: {status.reason}</Text> : null}
              <TouchableOpacity
                style={[styles.primaryBtn, { backgroundColor: COLORS.success, marginTop: 14 }]}
                onPress={handleCancelDeletion}
                disabled={cancelling}
              >
                {cancelling ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="refresh" size={18} color="#fff" />
                    <Text style={styles.primaryBtnText}>Cancel deletion</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.okRow}>
              <Ionicons name="checkmark-circle" size={18} color={COLORS.success} />
              <Text style={styles.okText}>No pending deletion. Your account is active.</Text>
            </View>
          )}
        </Card>

        {/* Export */}
        <Card style={styles.card}>
          <Text style={styles.cardTitle}>Export my data</Text>
          <Text style={styles.cardBody}>
            Download a JSON bundle of your personal data (decisions, journals, assessments, solutions, etc.).
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={handleExport} disabled={exporting}>
            {exporting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="download" size={18} color="#fff" />
                <Text style={styles.primaryBtnText}>Export JSON</Text>
              </>
            )}
          </TouchableOpacity>
        </Card>

        {/* Delete */}
        {status?.deletion_status !== 'pending' && (
          <Card style={[styles.card, styles.dangerCard]}>
            <Text style={[styles.cardTitle, { color: COLORS.error }]}>Delete my account</Text>
            <Text style={styles.cardBody}>
              Schedules permanent deletion of your account and personal data. You'll have a cooling-off period
              to cancel before data is purged.
            </Text>

            {!showDeleteForm ? (
              <TouchableOpacity
                style={[styles.primaryBtn, { backgroundColor: COLORS.error }]}
                onPress={() => setShowDeleteForm(true)}
              >
                <Ionicons name="trash" size={18} color="#fff" />
                <Text style={styles.primaryBtnText}>Request deletion</Text>
              </TouchableOpacity>
            ) : (
              <View style={{ marginTop: 8 }}>
                <Text style={styles.label}>Reason (optional)</Text>
                <TextInput
                  value={reason}
                  onChangeText={setReason}
                  placeholder="Help us improve (optional)"
                  placeholderTextColor={COLORS.textMuted}
                  style={styles.input}
                  multiline
                />

                <Text style={[styles.label, { marginTop: 12 }]}>
                  Type <Text style={{ fontWeight: '700' }}>DELETE MY ACCOUNT</Text> to confirm
                </Text>
                <TextInput
                  value={confirmPhrase}
                  onChangeText={setConfirmPhrase}
                  placeholder="DELETE MY ACCOUNT"
                  placeholderTextColor={COLORS.textMuted}
                  autoCapitalize="characters"
                  style={styles.input}
                />

                <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                  <TouchableOpacity
                    style={[styles.secondaryBtn, { flex: 1 }]}
                    onPress={() => {
                      setShowDeleteForm(false);
                      setConfirmPhrase('');
                      setReason('');
                    }}
                  >
                    <Text style={styles.secondaryBtnText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.primaryBtn,
                      { flex: 1, backgroundColor: COLORS.error, marginTop: 0 },
                    ]}
                    onPress={handleRequestDeletion}
                    disabled={deleting}
                  >
                    {deleting ? (
                      <ActivityIndicator color="#fff" />
                    ) : (
                      <Text style={styles.primaryBtnText}>Confirm</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </Card>
        )}

        <Text style={styles.footnote}>
          Contact the Data Protection Officer at privacy@viewdezider.app for any complaints.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: COLORS.white,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  scrollContent: { padding: 16, paddingBottom: 48 },
  introCard: {
    padding: 16,
    marginBottom: 16,
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  introRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  introTitle: { fontSize: 15, fontWeight: '700', color: '#065F46' },
  introText: { fontSize: 13, color: '#065F46', lineHeight: 19 },
  card: { padding: 16, marginBottom: 14 },
  dangerCard: { borderWidth: 1, borderColor: '#FEE2E2', backgroundColor: '#FFF5F5' },
  cardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  cardBody: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginBottom: 12 },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: COLORS.primary,
    borderRadius: 10,
    marginTop: 6,
    minHeight: 44,
  },
  primaryBtnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  secondaryBtn: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  secondaryBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    fontSize: 14,
    color: COLORS.textPrimary,
    backgroundColor: COLORS.white,
    minHeight: 44,
  },
  pendingBox: { marginTop: 8, padding: 12, backgroundColor: '#FFFBEB', borderRadius: 10, borderWidth: 1, borderColor: '#FCD34D' },
  pendingRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  pendingTitle: { fontSize: 14, fontWeight: '700', color: '#B45309' },
  pendingLine: { fontSize: 12, color: '#92400E', marginTop: 2 },
  okRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  okText: { fontSize: 13, color: COLORS.textSecondary },
  footnote: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 18, lineHeight: 16 },
});
