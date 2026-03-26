import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  StyleSheet, Alert, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444', warning: '#F59E0B',
};

const TYPE_COLORS: Record<string, string> = {
  PRODUCT: '#3B82F6', SERVICE: '#10B981', EVENT: '#F59E0B',
  PROJECT: '#8B5CF6', PERSON_CONTACT: '#EC4899',
};

export default function PendingApprovalsScreen() {
  const router = useRouter();
  const { session } = useAuthStore();
  const [pending, setPending] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  const fetchPending = useCallback(async () => {
    try {
      const res = await api.get('/solutions-store/pending-approval', {
        headers: { Authorization: `Bearer ${session}` },
      });
      setPending(res.data?.solutions || []);
    } catch (e: any) {
      if (e?.response?.status === 403) {
        Alert.alert('Access Denied', 'Admin access required');
        router.back();
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [session]);

  useEffect(() => { fetchPending(); }, [fetchPending]);

  const handleApprove = async (solutionId: string, name: string) => {
    Alert.alert(
      'Approve Solution',
      `Make "${name}" visible to all users?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Approve',
          style: 'default',
          onPress: async () => {
            try {
              await api.put(`/solutions-store/approve/${solutionId}`, {}, {
                headers: { Authorization: `Bearer ${session}` },
              });
              setPending(prev => prev.filter(s => s.solution_id !== solutionId));
              Alert.alert('Approved', `"${name}" is now publicly visible.`);
            } catch (e) {
              Alert.alert('Error', 'Failed to approve solution');
            }
          },
        },
      ],
    );
  };

  const handleReject = async (solutionId: string) => {
    if (!rejectReason.trim()) {
      return Alert.alert('Required', 'Please provide a reason for rejection');
    }
    try {
      await api.put(`/solutions-store/reject/${solutionId}`, { reason: rejectReason }, {
        headers: { Authorization: `Bearer ${session}` },
      });
      setPending(prev => prev.filter(s => s.solution_id !== solutionId));
      setRejectingId(null);
      setRejectReason('');
      Alert.alert('Rejected', 'Solution has been rejected.');
    } catch (e) {
      Alert.alert('Error', 'Failed to reject solution');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Pending Approvals</Text>
          <Text style={styles.headerSubtitle}>{pending.length} solution{pending.length !== 1 ? 's' : ''} awaiting review</Text>
        </View>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchPending(); }} tintColor={COLORS.primary} />}
      >
        {pending.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={48} color={COLORS.accent} />
            <Text style={styles.emptyTitle}>All clear!</Text>
            <Text style={styles.emptySubtitle}>No solutions pending approval</Text>
          </View>
        ) : (
          pending.map(sol => {
            const typeColor = TYPE_COLORS[sol.type] || COLORS.primary;
            const isRejecting = rejectingId === sol.solution_id;
            return (
              <View key={sol.solution_id} style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={[styles.typeBadge, { backgroundColor: typeColor + '20' }]}>
                    <Text style={[styles.typeText, { color: typeColor }]}>
                      {sol.type === 'PERSON_CONTACT' ? 'PERSON' : sol.type}
                    </Text>
                  </View>
                  <Text style={styles.dateText}>
                    {new Date(sol.created_at).toLocaleDateString()}
                  </Text>
                </View>

                <Text style={styles.solName}>{sol.name}</Text>
                <Text style={styles.solDesc} numberOfLines={3}>{sol.description}</Text>

                <View style={styles.metaRow}>
                  <View style={styles.metaItem}>
                    <Ionicons name="person-outline" size={13} color={COLORS.textMuted} />
                    <Text style={styles.metaText}>{sol.created_by_name || 'User'}</Text>
                  </View>
                  {sol.provider && (
                    <View style={styles.metaItem}>
                      <Ionicons name="business-outline" size={13} color={COLORS.textMuted} />
                      <Text style={styles.metaText}>{sol.provider}</Text>
                    </View>
                  )}
                  {sol.country && (
                    <View style={styles.metaItem}>
                      <Ionicons name="location-outline" size={13} color={COLORS.textMuted} />
                      <Text style={styles.metaText}>{sol.city || sol.state || sol.country}</Text>
                    </View>
                  )}
                </View>

                {sol.quantitative_factors?.length > 0 && (
                  <View style={styles.factorChips}>
                    {sol.quantitative_factors.map((f: any, i: number) => (
                      <View key={i} style={styles.factorChip}>
                        <Text style={styles.factorChipText}>{f.factor_name}: {f.value} {f.unit}</Text>
                      </View>
                    ))}
                  </View>
                )}

                {isRejecting ? (
                  <View style={styles.rejectForm}>
                    <TextInput
                      style={styles.rejectInput}
                      placeholder="Reason for rejection..."
                      placeholderTextColor={COLORS.textMuted}
                      value={rejectReason}
                      onChangeText={setRejectReason}
                      multiline
                    />
                    <View style={styles.rejectActions}>
                      <TouchableOpacity
                        style={styles.cancelRejectBtn}
                        onPress={() => { setRejectingId(null); setRejectReason(''); }}
                      >
                        <Text style={styles.cancelRejectText}>Cancel</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={styles.confirmRejectBtn}
                        onPress={() => handleReject(sol.solution_id)}
                      >
                        <Text style={styles.confirmRejectText}>Confirm Reject</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  <View style={styles.actionRow}>
                    <TouchableOpacity
                      style={styles.approveBtn}
                      onPress={() => handleApprove(sol.solution_id, sol.name)}
                    >
                      <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                      <Text style={styles.approveBtnText}>Approve</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.rejectBtn}
                      onPress={() => setRejectingId(sol.solution_id)}
                    >
                      <Ionicons name="close-circle" size={18} color={COLORS.danger} />
                      <Text style={styles.rejectBtnText}>Reject</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.detailBtn}
                      onPress={() => router.push(`/tools/solution-detail?solution_id=${sol.solution_id}`)}
                    >
                      <Ionicons name="eye" size={18} color={COLORS.primary} />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 16,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  backBtn: { marginRight: 12, padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: COLORS.text },
  headerSubtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginTop: 12 },
  emptySubtitle: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  card: {
    backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  typeBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 8 },
  typeText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  dateText: { fontSize: 11, color: COLORS.textMuted },
  solName: { fontSize: 16, fontWeight: '700', color: COLORS.text, marginBottom: 4 },
  solDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 8 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 8 },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 11, color: COLORS.textMuted },
  factorChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 10 },
  factorChip: { backgroundColor: COLORS.surfaceLight, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  factorChipText: { fontSize: 10, color: COLORS.textSecondary },
  actionRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  approveBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: COLORS.accent, paddingVertical: 10, borderRadius: 10,
  },
  approveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  rejectBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: COLORS.danger + '15', paddingVertical: 10, borderRadius: 10,
    borderWidth: 1, borderColor: COLORS.danger + '40',
  },
  rejectBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.danger },
  detailBtn: {
    padding: 10, borderRadius: 10,
    backgroundColor: COLORS.primary + '15', borderWidth: 1, borderColor: COLORS.primary + '40',
  },
  rejectForm: { marginTop: 4 },
  rejectInput: {
    backgroundColor: COLORS.surfaceLight, borderRadius: 10, padding: 12, minHeight: 60,
    color: COLORS.text, fontSize: 13, textAlignVertical: 'top',
    borderWidth: 1, borderColor: COLORS.danger + '40',
  },
  rejectActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancelRejectBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8,
    backgroundColor: COLORS.surfaceLight,
  },
  cancelRejectText: { fontSize: 13, color: COLORS.textSecondary },
  confirmRejectBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8,
    backgroundColor: COLORS.danger,
  },
  confirmRejectText: { fontSize: 13, fontWeight: '700', color: '#FFF' },
});
