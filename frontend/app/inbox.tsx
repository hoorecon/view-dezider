import React, { useState, useCallback } from 'react';
import { showAlert } from '../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Modal,
  ScrollView,
  TextInput,
  Alert,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';
import { safeBack } from '../src/utils/navigation';

interface SharedStep {
  id: string;
  decision_id: string;
  owner_id: string;
  owner_name: string;
  step_number: number;
  decision_title: string;
  decision_context: string;
  merge_mode: string;
  message: string;
  recipients: any[];
  step_data: {
    factors: any[];
    options: any[];
  };
  status: string;
  created_at: string;
}

const STEP_NAMES: Record<number, string> = {
  1: 'Context & Options', 2: 'List Factors', 3: 'Classify Factors',
  4: 'Prioritize Factors', 5: 'Calculate Ratings', 6: 'Define Options',
  7: 'Assess & Calculate', 8: 'Results Summary', 9: 'Reflection', 10: 'Final Notes',
};

export default function InboxScreen() {
  const router = useRouter();
  const [shares, setShares] = useState<SharedStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [contributeModal, setContributeModal] = useState<SharedStep | null>(null);
  const [assessments, setAssessments] = useState<Record<string, string>>({});
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchShares = async () => {
    try {
      const response = await api.get('/shared-steps/received');
      setShares(response.data);
    } catch (error) {
      console.error('Error fetching shares:', error);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchShares(); }, []));

  const onRefresh = async () => { setRefreshing(true); await fetchShares(); setRefreshing(false); };

  const getMyStatus = (share: SharedStep) => {
    const me = share.recipients?.find(r => r.status === 'contributed');
    return me ? 'contributed' : 'pending';
  };

  const openContribute = (share: SharedStep) => {
    setAssessments({});
    setNote('');
    setContributeModal(share);
  };

  const handleContribute = async () => {
    if (!contributeModal) return;
    setSubmitting(true);
    try {
      // Convert string values to numbers
      const numAssessments: Record<string, number> = {};
      for (const [key, val] of Object.entries(assessments)) {
        numAssessments[key] = parseInt(val, 10) || 50;
      }
      
      await api.post(`/shared-steps/${contributeModal.id}/contribute`, {
        assessments: numAssessments,
        note,
      });
      showAlert('Submitted!', 'Your contribution has been submitted');
      setContributeModal(null);
      fetchShares();
    } catch (error: any) {
      showAlert('Error', error.response?.data?.detail || 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const renderShare = ({ item }: { item: SharedStep }) => {
    const myStatus = getMyStatus(item);
    const isContributed = myStatus === 'contributed';
    return (
      <View style={[styles.shareCard, isContributed && styles.shareCardDone]}>
        <View style={styles.shareHeader}>
          <View style={styles.stepBadge}>
            <Text style={styles.stepBadgeText}>Step {item.step_number}</Text>
          </View>
          <View style={[
            styles.statusBadge,
            isContributed ? styles.statusDone : styles.statusPending,
          ]}>
            <Ionicons
              name={isContributed ? 'checkmark-circle' : 'time-outline'}
              size={12}
              color={isContributed ? '#10B981' : '#F59E0B'}
            />
            <Text style={[
              styles.statusText,
              { color: isContributed ? '#10B981' : '#F59E0B' },
            ]}>{isContributed ? 'Contributed' : 'Pending'}</Text>
          </View>
        </View>

        <Text style={styles.shareTitle}>{item.decision_title}</Text>
        <Text style={styles.shareStep}>{STEP_NAMES[item.step_number] || `Step ${item.step_number}`}</Text>

        <View style={styles.shareFrom}>
          <Ionicons name="person-outline" size={13} color={COLORS.textMuted} />
          <Text style={styles.shareFromText}>From: {item.owner_name}</Text>
        </View>

        {item.message ? (
          <View style={styles.messageBox}>
            <Text style={styles.messageText}>"{item.message}"</Text>
          </View>
        ) : null}

        {/* Show factors/options context */}
        {item.step_data?.factors?.length > 0 && (
          <View style={styles.contextBox}>
            <Text style={styles.contextLabel}>Factors:</Text>
            <View style={styles.chipRow}>
              {item.step_data.factors.map((f: any) => (
                <View key={f.id} style={styles.chip}>
                  <Text style={styles.chipText}>{f.name}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {item.step_data?.options?.length > 0 && (
          <View style={styles.contextBox}>
            <Text style={styles.contextLabel}>Options:</Text>
            <View style={styles.chipRow}>
              {item.step_data.options.map((o: any) => (
                <View key={o.id} style={[styles.chip, styles.chipOption]}>
                  <Text style={[styles.chipText, styles.chipOptionText]}>{o.name}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={styles.shareFooter}>
          <Text style={styles.shareTime}>{formatTime(item.created_at)}</Text>
          {!isContributed && item.status === 'active' && (
            <TouchableOpacity style={styles.contributeBtn} onPress={() => openContribute(item)}>
              <Ionicons name="create-outline" size={16} color="#FFF" />
              <Text style={styles.contributeBtnText}>Contribute</Text>
            </TouchableOpacity>
          )}
          {item.status === 'merged' && (
            <View style={styles.mergedBadge}>
              <Ionicons name="git-merge" size={12} color="#8B5CF6" />
              <Text style={styles.mergedText}>Merged</Text>
            </View>
          )}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Shared Inbox</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{shares.filter(s => getMyStatus(s) === 'pending').length} pending</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <FlatList
          data={shares}
          renderItem={renderShare}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="mail-open-outline" size={56} color={COLORS.textMuted} />
              <Text style={styles.emptyTitle}>No Shared Steps</Text>
              <Text style={styles.emptyText}>When someone shares a decision step with you for input, it will appear here</Text>
            </View>
          }
        />
      )}

      {/* Contribute Modal */}
      <Modal
        visible={!!contributeModal}
        animationType="slide"
        transparent
        onRequestClose={() => setContributeModal(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Your Contribution</Text>
              <TouchableOpacity onPress={() => setContributeModal(null)} style={styles.closeBtn}>
                <Ionicons name="close" size={22} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
              {contributeModal && (
                <>
                  <Text style={styles.modalSubtitle}>
                    Rate each factor for: {contributeModal.decision_title}
                  </Text>

                  {/* Assessment Grid */}
                  {contributeModal.step_data?.options?.map((option: any) => (
                    <View key={option.id} style={styles.optionSection}>
                      <Text style={styles.optionName}>{option.name}</Text>
                      {contributeModal.step_data?.factors?.map((factor: any) => {
                        const key = `${option.id}_${factor.id}`;
                        return (
                          <View key={key} style={styles.assessRow}>
                            <Text style={styles.factorLabel}>{factor.name}</Text>
                            <View style={styles.lmhRow}>
                              {(['L', 'M', 'H'] as const).map(mode => {
                                const vals = { L: '25', M: '50', H: '75' };
                                const isActive = assessments[key] === vals[mode];
                                return (
                                  <TouchableOpacity
                                    key={mode}
                                    style={[styles.lmhBtn, isActive && styles.lmhBtnActive]}
                                    onPress={() => setAssessments(prev => ({ ...prev, [key]: vals[mode] }))}
                                  >
                                    <Text style={[styles.lmhText, isActive && styles.lmhTextActive]}>
                                      {mode === 'L' ? 'Low' : mode === 'M' ? 'Med' : 'High'}
                                    </Text>
                                  </TouchableOpacity>
                                );
                              })}
                              <TextInput
                                style={styles.customInput}
                                value={assessments[key] || ''}
                                onChangeText={v => setAssessments(prev => ({ ...prev, [key]: v }))}
                                keyboardType="numeric"
                                maxLength={3}
                                placeholder="%"
                                placeholderTextColor={COLORS.textMuted}
                              />
                            </View>
                          </View>
                        );
                      })}
                    </View>
                  ))}

                  {/* Note */}
                  <View style={styles.noteSection}>
                    <Text style={styles.noteLabel}>Notes (optional)</Text>
                    <TextInput
                      style={styles.noteInput}
                      value={note}
                      onChangeText={setNote}
                      placeholder="Share your thoughts..."
                      placeholderTextColor={COLORS.textMuted}
                      multiline
                      numberOfLines={3}
                    />
                  </View>

                  <TouchableOpacity
                    style={[styles.submitBtn, submitting && styles.submitBtnDisabled]}
                    onPress={handleContribute}
                    disabled={submitting}
                  >
                    {submitting ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <>
                        <Ionicons name="send" size={18} color="#FFF" />
                        <Text style={styles.submitBtnText}>Submit Contribution</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.white, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { flex: 1, fontSize: 22, fontWeight: '700', color: COLORS.textPrimary },
  countBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: 'rgba(245,158,11,0.12)' },
  countText: { fontSize: 11, fontWeight: '600', color: '#F59E0B' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  list: { padding: 16, paddingTop: 0, flexGrow: 1 },

  // Share cards
  shareCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  shareCardDone: { borderColor: 'rgba(16,185,129,0.2)', backgroundColor: 'rgba(16,185,129,0.02)' },
  shareHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  stepBadge: { backgroundColor: COLORS.primary, paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  stepBadgeText: { fontSize: 11, fontWeight: '700', color: '#FFF' },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  statusDone: { backgroundColor: 'rgba(16,185,129,0.1)' },
  statusPending: { backgroundColor: 'rgba(245,158,11,0.1)' },
  statusText: { fontSize: 11, fontWeight: '600' },
  shareTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 2 },
  shareStep: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 6 },
  shareFrom: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 },
  shareFromText: { fontSize: 12, color: COLORS.textMuted },
  messageBox: { backgroundColor: 'rgba(142,36,170,0.04)', borderRadius: 8, padding: 8, marginVertical: 6 },
  messageText: { fontSize: 12, color: COLORS.textSecondary, fontStyle: 'italic' },
  contextBox: { marginTop: 6 },
  contextLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted, marginBottom: 4 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  chip: { backgroundColor: COLORS.background, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  chipText: { fontSize: 10, color: COLORS.textSecondary, fontWeight: '500' },
  chipOption: { backgroundColor: 'rgba(99,102,241,0.08)' },
  chipOptionText: { color: '#6366F1' },
  shareFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 },
  shareTime: { fontSize: 11, color: COLORS.textMuted },
  contributeBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  contributeBtnText: { fontSize: 13, fontWeight: '600', color: '#FFF' },
  mergedBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10, backgroundColor: 'rgba(139,92,246,0.1)' },
  mergedText: { fontSize: 11, fontWeight: '600', color: '#8B5CF6' },

  // Empty
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },
  emptyText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, maxWidth: 260 },

  // Contribute Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalContainer: { backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '90%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  closeBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center' },
  modalBody: { padding: 16 },
  modalSubtitle: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 16, lineHeight: 18 },

  // Assessment
  optionSection: { marginBottom: 16, padding: 12, backgroundColor: COLORS.background, borderRadius: 12 },
  optionName: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 10 },
  assessRow: { marginBottom: 10 },
  factorLabel: { fontSize: 13, fontWeight: '500', color: COLORS.textPrimary, marginBottom: 5 },
  lmhRow: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  lmhBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  lmhBtnActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  lmhText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  lmhTextActive: { color: '#FFF' },
  customInput: { width: 50, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, textAlign: 'center', paddingVertical: 4, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },

  noteSection: { marginTop: 8, marginBottom: 16 },
  noteLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 6 },
  noteInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, minHeight: 60, textAlignVertical: 'top' },

  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, paddingVertical: 14, borderRadius: 12, marginBottom: 24 },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
});
