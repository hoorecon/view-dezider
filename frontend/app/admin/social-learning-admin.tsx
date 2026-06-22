import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Modal,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const LIFE_AREA_LABELS: Record<string, string> = {
  career_profession: 'Career', finance_wealth: 'Finance', health_wellness: 'Health',
  relationships_family: 'Relationships', education_learning: 'Education',
  personal_growth: 'Personal Growth', social_community: 'Social',
  legal_governance: 'Legal', technology_innovation: 'Technology',
  environment_sustainability: 'Environment',
};

export default function SocialLearningAdminScreen() {
  const router = useRouter();
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Approval modal
  const [approvalModal, setApprovalModal] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [adminNotes, setAdminNotes] = useState('');
  const [approving, setApproving] = useState(false);
  const [selectedAction, setSelectedAction] = useState<'authorized' | 'rejected'>('authorized');

  // Synthesis modal
  const [synthModal, setSynthModal] = useState(false);
  const [authorizedList, setAuthorizedList] = useState<any[]>([]);
  const [synthSelected, setSynthSelected] = useState<Set<string>>(new Set());
  const [synthesizing, setSynthesizing] = useState(false);
  const [synthLifeArea, setSynthLifeArea] = useState('');

  const fetchPending = async () => {
    setLoading(true);
    try {
      const res = await api.get('/social-learning/admin/pending', { params: { limit: 50 } });
      setTemplates(res.data?.templates || []);
    } catch (e: any) {
      if (e.response?.status === 403) {
        showAlert('Access Denied', 'Admin access required for this section.');
      }
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchPending(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchPending();
    setRefreshing(false);
  };

  const openApproval = (id: string, action: 'authorized' | 'rejected') => {
    setSelectedId(id);
    setSelectedAction(action);
    setAdminNotes('');
    setApprovalModal(true);
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await api.post(`/social-learning/admin/approve/${selectedId}`, {
        status: selectedAction,
        admin_notes: adminNotes,
      });
      showAlert('Done', `Template ${selectedAction === 'authorized' ? 'approved' : 'rejected'}!`);
      setApprovalModal(false);
      fetchPending();
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to process');
    } finally {
      setApproving(false);
    }
  };

  // Synthesis
  const openSynthesis = async () => {
    try {
      const res = await api.get('/social-learning/authorized', { params: { limit: 100 } });
      setAuthorizedList(res.data?.templates || []);
      setSynthSelected(new Set());
      setSynthLifeArea('');
      setSynthModal(true);
    } catch (e) {
      showAlert('Error', 'Failed to load authorized templates');
    }
  };

  const toggleSynthSelect = (id: string) => {
    const newSet = new Set(synthSelected);
    if (newSet.has(id)) newSet.delete(id); else newSet.add(id);
    setSynthSelected(newSet);
  };

  const handleSynthesize = async () => {
    if (synthSelected.size < 2) {
      showAlert('Minimum 2', 'Select at least 2 authorized templates to synthesize.');
      return;
    }
    setSynthesizing(true);
    try {
      const res = await api.post('/social-learning/admin/synthesize', {
        template_ids: Array.from(synthSelected),
        target_life_area: synthLifeArea || undefined,
      });
      showAlert('Synthesized!', `Premium template "${res.data?.title || 'N/A'}" created from ${synthSelected.size} sources.`);
      setSynthModal(false);
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Synthesis failed');
    } finally {
      setSynthesizing(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.header} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Social Learning Admin</Text>
          <Text style={styles.headerSub}>{templates.length} pending review</Text>
        </View>
        <TouchableOpacity style={styles.synthBtn} onPress={openSynthesis}>
          <Ionicons name="sparkles" size={18} color="#7C3AED" />
        </TouchableOpacity>
      </LinearGradient>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Synthesize button */}
        <TouchableOpacity style={styles.synthCard} onPress={openSynthesis}>
          <LinearGradient colors={['#7C3AED', '#5B21B6']} style={styles.synthCardGrad}>
            <Ionicons name="sparkles" size={20} color="#FFF" />
            <View style={{ flex: 1 }}>
              <Text style={styles.synthCardTitle}>Synthesize Premium Templates</Text>
              <Text style={styles.synthCardSub}>Combine 2+ authorized templates into AI-powered premium content</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
          </LinearGradient>
        </TouchableOpacity>

        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : templates.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={48} color={COLORS.success} />
            <Text style={styles.emptyTitle}>All caught up!</Text>
            <Text style={styles.emptyText}>No templates pending review</Text>
          </View>
        ) : (
          templates.map((t: any) => (
            <View key={t.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={[styles.catBadge, { backgroundColor: t.category === 'problem' ? '#FEF2F2' : t.category === 'need' ? '#FFFBEB' : '#ECFDF5' }]}>
                  <Text style={[styles.catText, { color: t.category === 'problem' ? '#EF4444' : t.category === 'need' ? '#D97706' : '#059669' }]}>
                    {t.category}
                  </Text>
                </View>
                <Text style={styles.cardLang}>{t.detected_language}</Text>
                {t.severity_score && (
                  <Text style={[styles.severityBadge, {
                    color: t.severity_score >= 7 ? '#EF4444' : t.severity_score >= 4 ? '#D97706' : '#059669'
                  }]}>
                    Severity: {t.severity_score}/10
                  </Text>
                )}
              </View>

              <Text style={styles.cardTitle}>{t.title}</Text>
              <Text style={styles.cardSummary} numberOfLines={3}>{t.english_summary}</Text>

              {(t.life_areas || []).length > 0 && (
                <View style={styles.tagRow}>
                  {(t.life_areas || []).slice(0, 4).map((la: string) => (
                    <View key={la} style={styles.tag}>
                      <Text style={styles.tagText}>{LIFE_AREA_LABELS[la] || la}</Text>
                    </View>
                  ))}
                </View>
              )}

              {(t.factors || []).length > 0 && (
                <Text style={styles.factorCount}>{t.factors.length} factors • {(t.concerns || []).length} concerns</Text>
              )}

              <View style={styles.cardActions}>
                <TouchableOpacity
                  style={styles.approveBtn}
                  onPress={() => openApproval(t.id, 'authorized')}
                >
                  <Ionicons name="checkmark-circle" size={16} color="#FFF" />
                  <Text style={styles.approveBtnText}>Authorize</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.rejectBtn}
                  onPress={() => openApproval(t.id, 'rejected')}
                >
                  <Ionicons name="close-circle" size={16} color="#EF4444" />
                  <Text style={styles.rejectBtnText}>Reject</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Approval Modal */}
      <Modal visible={approvalModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>
              {selectedAction === 'authorized' ? 'Authorize Template' : 'Reject Template'}
            </Text>
            <Text style={styles.modalSub}>
              {selectedAction === 'authorized'
                ? 'This will make it a Tier 2 Authorized template visible to all users.'
                : 'Provide a reason for rejection.'}
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Admin notes (optional)"
              placeholderTextColor={COLORS.textMuted}
              value={adminNotes}
              onChangeText={setAdminNotes}
              multiline
              numberOfLines={3}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancel}
                onPress={() => setApprovalModal(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.modalConfirm,
                  { backgroundColor: selectedAction === 'authorized' ? '#059669' : '#EF4444' },
                ]}
                onPress={handleApprove}
                disabled={approving}
              >
                {approving ? (
                  <ActivityIndicator color="#FFF" size="small" />
                ) : (
                  <Text style={styles.modalConfirmText}>
                    {selectedAction === 'authorized' ? 'Authorize' : 'Reject'}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Synthesis Modal */}
      <Modal visible={synthModal} transparent animationType="slide">
        <View style={styles.synthOverlay}>
          <View style={styles.synthContent}>
            <View style={styles.synthHeader}>
              <Ionicons name="sparkles" size={20} color="#7C3AED" />
              <Text style={styles.synthTitle}>AI Synthesis</Text>
              <View style={{ flex: 1 }} />
              <TouchableOpacity onPress={() => setSynthModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>

            <Text style={styles.synthDesc}>
              Select 2+ authorized templates to synthesize into a premium AI-powered template.
            </Text>

            <Text style={styles.synthLabel}>Selected: {synthSelected.size}</Text>

            <ScrollView style={{ maxHeight: 300 }} showsVerticalScrollIndicator={false}>
              {authorizedList.length === 0 ? (
                <Text style={styles.noAuth}>No authorized templates available yet.</Text>
              ) : (
                authorizedList.map((t: any) => (
                  <TouchableOpacity
                    key={t.id}
                    style={[styles.synthRow, synthSelected.has(t.id) && styles.synthRowActive]}
                    onPress={() => toggleSynthSelect(t.id)}
                  >
                    <Ionicons
                      name={synthSelected.has(t.id) ? 'checkmark-circle' : 'ellipse-outline'}
                      size={20}
                      color={synthSelected.has(t.id) ? '#059669' : '#D1D5DB'}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.synthRowTitle} numberOfLines={1}>{t.title}</Text>
                      <Text style={styles.synthRowMeta}>
                        {t.category} • {(t.life_areas || []).slice(0, 2).map((la: string) => LIFE_AREA_LABELS[la] || la).join(', ')}
                      </Text>
                    </View>
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>

            <TouchableOpacity
              style={[styles.synthLaunch, synthSelected.size < 2 && { opacity: 0.5 }]}
              onPress={handleSynthesize}
              disabled={synthesizing || synthSelected.size < 2}
            >
              {synthesizing ? (
                <ActivityIndicator color="#FFF" size="small" />
              ) : (
                <>
                  <Ionicons name="sparkles" size={16} color="#FFF" />
                  <Text style={styles.synthLaunchText}>
                    Synthesize {synthSelected.size} Templates
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 20 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  synthBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center' },

  synthCard: { borderRadius: 12, overflow: 'hidden', marginBottom: 16 },
  synthCardGrad: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  synthCardTitle: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  synthCardSub: { fontSize: 11, color: 'rgba(255,255,255,0.8)', marginTop: 2 },

  emptyState: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: COLORS.textSecondary },
  emptyText: { fontSize: 13, color: COLORS.textMuted },

  card: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  catBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  catText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  cardLang: { fontSize: 11, color: COLORS.textMuted, textTransform: 'capitalize' },
  severityBadge: { fontSize: 11, fontWeight: '600' },
  cardTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  cardSummary: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 17, marginBottom: 8 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 },
  tag: { backgroundColor: '#F0E6FF', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  tagText: { fontSize: 9, color: '#7C3AED', fontWeight: '500' },
  factorCount: { fontSize: 11, color: COLORS.textMuted, marginBottom: 8 },

  cardActions: { flexDirection: 'row', gap: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border },
  approveBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#059669', borderRadius: 10, paddingVertical: 10 },
  approveBtnText: { fontSize: 13, fontWeight: '600', color: '#FFF' },
  rejectBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#FEF2F2', borderRadius: 10, paddingVertical: 10, borderWidth: 1, borderColor: '#FECACA' },
  rejectBtnText: { fontSize: 13, fontWeight: '600', color: '#EF4444' },

  // Approval Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalContent: { width: '100%', maxWidth: 400, backgroundColor: '#FFF', borderRadius: 16, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  modalSub: { fontSize: 13, color: COLORS.textMuted, marginBottom: 16 },
  modalInput: { backgroundColor: COLORS.background, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, minHeight: 80, textAlignVertical: 'top', marginBottom: 16 },
  modalActions: { flexDirection: 'row', gap: 10 },
  modalCancel: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 10, backgroundColor: COLORS.background },
  modalCancelText: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary },
  modalConfirm: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 10 },
  modalConfirmText: { fontSize: 14, fontWeight: '600', color: '#FFF' },

  // Synthesis Modal
  synthOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  synthContent: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '80%' },
  synthHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  synthTitle: { fontSize: 18, fontWeight: '700', color: '#1F2937' },
  synthDesc: { fontSize: 13, color: COLORS.textMuted, marginBottom: 12 },
  synthLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 8 },
  noAuth: { fontSize: 13, color: COLORS.textMuted, fontStyle: 'italic', textAlign: 'center', paddingVertical: 20 },
  synthRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 8, backgroundColor: '#F9FAFB', marginBottom: 4 },
  synthRowActive: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  synthRowTitle: { fontSize: 13, fontWeight: '600', color: '#374151' },
  synthRowMeta: { fontSize: 10, color: '#9CA3AF', marginTop: 1 },
  synthLaunch: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 14, marginTop: 12 },
  synthLaunchText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
