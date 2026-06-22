import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const ACTION_ICONS: Record<string, {icon: string; color: string}> = {
  digilocker_status_check: { icon: 'card', color: '#6366F1' },
  digilocker_initiate: { icon: 'card', color: '#6366F1' },
  digilocker_initiate_failed: { icon: 'card', color: '#DC2626' },
  biometric_verified: { icon: 'finger-print', color: '#059669' },
  biometric_verify_failed: { icon: 'finger-print', color: '#DC2626' },
  totp_verified: { icon: 'key', color: '#059669' },
  totp_verify_failed: { icon: 'key', color: '#DC2626' },
  incident_created: { icon: 'warning', color: '#EA580C' },
  incident_updated: { icon: 'create', color: '#D97706' },
  certin_notified: { icon: 'megaphone', color: '#DC2626' },
  users_notified: { icon: 'people', color: '#7C3AED' },
  audit_purge: { icon: 'trash', color: '#6B7280' },
};

export default function AuditTrailScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<any>(null);
  const [filter, setFilter] = useState<'all' | 'kyc' | 'sensitive'>('all');
  const [page, setPage] = useState(0);

  const fetchData = async (currentFilter = filter, currentPage = 0) => {
    try {
      let endpoint = '/audit-trail';
      const params: any = { limit: 30, skip: currentPage * 30 };

      if (currentFilter === 'kyc') endpoint = '/audit-trail/kyc';
      if (currentFilter === 'sensitive') params.sensitive_only = true;

      const [logsRes, statsRes] = await Promise.all([
        api.get(endpoint, { params }),
        api.get('/audit-trail/stats').catch(() => ({ data: null })),
      ]);
      setLogs(logsRes.data?.logs || []);
      setTotal(logsRes.data?.total || 0);
      setStats(statsRes.data);
    } catch (err: any) {
      if (err.response?.status !== 403) showAlert('Error', err.response?.data?.detail || 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const changeFilter = (f: 'all' | 'kyc' | 'sensitive') => {
    setFilter(f);
    setPage(0);
    setLoading(true);
    fetchData(f, 0);
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#1F2937" /></View>;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#1F2937', '#374151']} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>KYC Audit Trail</Text>
          <Text style={styles.headerSub}>DPDPA 2023 • UIDAI Compliant</Text>
        </View>
        <View style={styles.totalBadge}>
          <Text style={styles.totalText}>{total}</Text>
        </View>
      </LinearGradient>

      {/* Stats */}
      {stats && (
        <View style={styles.statsRow}>
          <View style={[styles.statChip, { backgroundColor: '#F3F4F6' }]}>
            <Text style={styles.statChipNum}>{stats.total_events}</Text>
            <Text style={styles.statChipLabel}>Total</Text>
          </View>
          <View style={[styles.statChip, { backgroundColor: '#FEF2F2' }]}>
            <Text style={[styles.statChipNum, { color: '#DC2626' }]}>{stats.sensitive_accesses}</Text>
            <Text style={styles.statChipLabel}>Sensitive</Text>
          </View>
          <View style={[styles.statChip, { backgroundColor: '#EEF2FF' }]}>
            <Text style={[styles.statChipNum, { color: '#6366F1' }]}>{stats.kyc_related}</Text>
            <Text style={styles.statChipLabel}>KYC</Text>
          </View>
          <View style={[styles.statChip, { backgroundColor: '#FFF7ED' }]}>
            <Text style={[styles.statChipNum, { color: '#F97316' }]}>{stats.last_24h}</Text>
            <Text style={styles.statChipLabel}>24h</Text>
          </View>
        </View>
      )}

      {/* Filters */}
      <View style={styles.filterRow}>
        {[
          { key: 'all', label: 'All Events' },
          { key: 'kyc', label: 'KYC Only' },
          { key: 'sensitive', label: 'Sensitive' },
        ].map(f => (
          <TouchableOpacity key={f.key}
            style={[styles.filterBtn, filter === f.key && styles.filterActive]}
            onPress={() => changeFilter(f.key as any)}>
            <Text style={[styles.filterText, filter === f.key && { color: '#FFF' }]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.body} refreshControl={<RefreshControl refreshing={false} onRefresh={() => fetchData()} />}>
        {logs.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="eye-off" size={40} color="#D1D5DB" />
            <Text style={styles.emptyText}>No audit events found</Text>
          </View>
        ) : (
          logs.map((log: any, idx: number) => {
            const ai = ACTION_ICONS[log.action] || { icon: 'ellipse', color: '#9CA3AF' };
            return (
              <View key={log.id || idx} style={styles.logCard}>
                <View style={[styles.logIcon, { backgroundColor: ai.color + '15' }]}>
                  <Ionicons name={ai.icon as any} size={16} color={ai.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={styles.logHeaderRow}>
                    <Text style={styles.logAction}>{(log.action || '').replace(/_/g, ' ')}</Text>
                    {log.sensitive_data_accessed && (
                      <View style={styles.sensitiveBadge}>
                        <Ionicons name="lock-closed" size={8} color="#DC2626" />
                        <Text style={styles.sensitiveText}>SENSITIVE</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.logDetails} numberOfLines={2}>{log.details}</Text>
                  <View style={styles.logMeta}>
                    <Text style={styles.logMetaText}>{log.entity_type}/{log.entity_id?.slice(0, 12)}</Text>
                    {log.ip_address ? <Text style={styles.logMetaText}>IP: {log.ip_address.slice(0, 15)}</Text> : null}
                    <Text style={styles.logTime}>
                      {new Date(log.timestamp).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </Text>
                  </View>
                  {log.data_fields_accessed?.length > 0 && (
                    <View style={styles.fieldsRow}>
                      {log.data_fields_accessed.map((f: string, i: number) => (
                        <View key={i} style={styles.fieldTag}>
                          <Text style={styles.fieldTagText}>{f}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              </View>
            );
          })
        )}

        {/* Pagination */}
        {total > 30 && (
          <View style={styles.pagination}>
            <TouchableOpacity style={[styles.pageBtn, page === 0 && { opacity: 0.3 }]}
              onPress={() => { if (page > 0) { setPage(page - 1); fetchData(filter, page - 1); } }} disabled={page === 0}>
              <Ionicons name="chevron-back" size={16} color="#374151" />
              <Text style={styles.pageBtnText}>Prev</Text>
            </TouchableOpacity>
            <Text style={styles.pageInfo}>Page {page + 1} of {Math.ceil(total / 30)}</Text>
            <TouchableOpacity style={[styles.pageBtn, (page + 1) * 30 >= total && { opacity: 0.3 }]}
              onPress={() => { if ((page + 1) * 30 < total) { setPage(page + 1); fetchData(filter, page + 1); } }}
              disabled={(page + 1) * 30 >= total}>
              <Text style={styles.pageBtnText}>Next</Text>
              <Ionicons name="chevron-forward" size={16} color="#374151" />
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.1)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 2 },
  totalBadge: { backgroundColor: 'rgba(255,255,255,0.15)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  totalText: { fontSize: 14, fontWeight: '800', color: '#FFF' },

  statsRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingTop: 12 },
  statChip: { flex: 1, alignItems: 'center', padding: 10, borderRadius: 10 },
  statChipNum: { fontSize: 16, fontWeight: '800', color: '#1F2937' },
  statChipLabel: { fontSize: 9, color: '#9CA3AF', marginTop: 2 },

  filterRow: { flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 },
  filterBtn: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 8, backgroundColor: '#F3F4F6' },
  filterActive: { backgroundColor: '#1F2937' },
  filterText: { fontSize: 12, fontWeight: '600', color: '#6B7280' },

  body: { flex: 1, paddingHorizontal: 16 },

  emptyState: { alignItems: 'center', paddingVertical: 60, gap: 8 },
  emptyText: { fontSize: 14, color: '#9CA3AF' },

  logCard: { flexDirection: 'row', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#F3F4F6' },
  logIcon: { width: 32, height: 32, borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginTop: 2 },
  logHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 },
  logAction: { fontSize: 12, fontWeight: '700', color: '#374151', textTransform: 'capitalize' },
  sensitiveBadge: { flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: '#FEF2F2', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  sensitiveText: { fontSize: 8, fontWeight: '700', color: '#DC2626' },
  logDetails: { fontSize: 11, color: '#6B7280', lineHeight: 16, marginBottom: 4 },
  logMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  logMetaText: { fontSize: 9, color: '#9CA3AF' },
  logTime: { fontSize: 9, color: '#9CA3AF' },
  fieldsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 },
  fieldTag: { backgroundColor: '#EEF2FF', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  fieldTagText: { fontSize: 9, fontWeight: '600', color: '#6366F1' },

  pagination: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 16, paddingVertical: 16 },
  pageBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#F3F4F6' },
  pageBtnText: { fontSize: 12, fontWeight: '600', color: '#374151' },
  pageInfo: { fontSize: 12, color: '#9CA3AF' },
});
