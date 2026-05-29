/**
 * Pros & Cons — Listing screen.
 *
 * Mirrors /tools/swot list view but for Pros & Cons (8-step) analyses.
 * - Shows all user Pros & Cons analyses (most recent first)
 * - "+" header button → creates a fresh analysis and jumps into the wizard
 * - Tap a row → opens the wizard at /tools/pros-cons-wizard?id=<id>&module=pros-cons
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, Modal,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { LIFE_AREAS as LIFE_AREAS_CANONICAL } from '../../src/constants/lifeAreas';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';

interface ProsConsAnalysis {
  id: string;
  title: string;
  context?: string;
  life_area?: string | null;
  options?: any[];
  factors?: any[];
  pros?: any[];
  cons?: any[];
  current_step?: number;
  converted_decision_id?: string | null;
  created_at: string;
  updated_at?: string;
}

const LIFE_AREAS = LIFE_AREAS_CANONICAL.map(a => ({ key: a.id, label: a.short, icon: a.icon }));
const LIFE_AREA_LABELS: Record<string, { short: string; icon: string }> = LIFE_AREAS_CANONICAL.reduce(
  (acc: any, a: any) => { acc[a.id] = { short: a.short, icon: a.icon }; return acc; }, {}
);

function getStatus(p: ProsConsAnalysis): { label: string; color: string; bg: string } {
  const step = p.current_step || 1;
  const totalPC = (p.options || []).reduce((sum: number, o: any) => sum + ((o.pros || []).length + (o.cons || []).length), 0)
                + (p.pros || []).length + (p.cons || []).length;
  if (step >= 8) return { label: 'Completed', color: '#059669', bg: '#ECFDF5' };
  if (step > 1 || totalPC > 0) return { label: 'In Progress', color: '#D97706', bg: '#FFFBEB' };
  return { label: 'Draft', color: '#6B7280', bg: '#F3F4F6' };
}

export default function ProsConsListScreen() {
  const router = useRouter();
  const [items, setItems] = useState<ProsConsAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContext, setNewContext] = useState('');
  const [newLifeArea, setNewLifeArea] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchItems = async () => {
    try {
      const res = await api.get('/pros-cons');
      const all: ProsConsAnalysis[] = res.data || [];
      all.sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
      setItems(all);
    } catch (err) {
      console.error('Error fetching pros-cons:', err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchItems(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchItems();
    setRefreshing(false);
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) {
      showAlert('Required', 'Please enter a title for your Pros & Cons analysis');
      return;
    }
    setCreating(true);
    try {
      const res = await api.post('/pros-cons', {
        title: newTitle.trim(),
        context: newContext.trim(),
        life_area: newLifeArea || null,
      });
      const newId = res.data?.id;
      setShowCreateModal(false);
      setNewTitle(''); setNewContext(''); setNewLifeArea('');
      if (newId) {
        router.push(`/tools/pros-cons-wizard?id=${newId}&module=pros-cons` as any);
      }
    } catch (e) {
      showAlert('Create Failed', 'Could not create the analysis. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    showAlert(
      'Delete Analysis?',
      'This will permanently remove this Pros & Cons analysis.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete', style: 'destructive', onPress: async () => {
            try {
              await api.delete(`/pros-cons/${id}`);
              setItems(prev => prev.filter(it => it.id !== id));
            } catch {
              showAlert('Delete Failed', 'Could not delete. Please try again.');
            }
          }
        }
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <LinearGradient
        colors={['#7C3AED', '#A855F7']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Pros & Cons</Text>
          <Text style={styles.headerSub}>Deep 8-step framework</Text>
        </View>
        <TouchableOpacity
          style={styles.createBtnHeader}
          onPress={() => router.push('/tools/new-decision?module=pros-cons' as any)}
        >
          <Ionicons name="add" size={22} color="#7C3AED" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          showsVerticalScrollIndicator={false}
        >
          {/* How it works */}
          <View style={styles.howItWorks}>
            <Ionicons name="bulb-outline" size={20} color="#7C3AED" />
            <Text style={styles.howItWorksText}>
              Compare options through pros, cons, factor classification, and weighted scoring.
              For a holistic view across all life areas, head to Solution Box.
            </Text>
          </View>

          {items.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="layers-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyStateTitle}>No Pros & Cons Yet</Text>
              <Text style={styles.emptyStateText}>
                Create your first analysis to weigh options across pros, cons & factors.
              </Text>
              <TouchableOpacity
                style={styles.emptyCreateBtn}
                onPress={() => router.push('/tools/new-decision?module=pros-cons' as any)}
              >
                <Ionicons name="add" size={20} color="#FFF" />
                <Text style={styles.emptyCreateText}>New Pros & Cons</Text>
              </TouchableOpacity>
            </View>
          ) : (
            items.map(p => {
              const status = getStatus(p);
              const totalPros = (p.options || []).reduce((s: number, o: any) => s + (o.pros || []).length, 0)
                              + (p.pros || []).length;
              const totalCons = (p.options || []).reduce((s: number, o: any) => s + (o.cons || []).length, 0)
                              + (p.cons || []).length;
              const lifeMeta = LIFE_AREA_LABELS[p.life_area || ''];
              return (
                <TouchableOpacity
                  key={p.id}
                  style={styles.listCard}
                  onPress={() => router.push(`/tools/pros-cons-wizard?id=${p.id}&module=pros-cons` as any)}
                  activeOpacity={0.7}
                >
                  <View style={styles.listCardHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.listCardTitle} numberOfLines={1}>{p.title || 'Untitled Analysis'}</Text>
                      {p.context ? <Text style={styles.listCardContext} numberOfLines={1}>{p.context}</Text> : null}
                    </View>
                    <View style={[styles.statusBadge, { backgroundColor: status.bg }]}>
                      <Text style={[styles.statusBadgeText, { color: status.color }]}>{status.label}</Text>
                    </View>
                  </View>

                  {/* Pros / Cons mini grid */}
                  <View style={styles.miniGrid}>
                    <View style={[styles.miniCell, { backgroundColor: '#ECFDF5' }]}>
                      <Ionicons name="thumbs-up" size={12} color="#059669" />
                      <Text style={[styles.miniCellNum, { color: '#059669' }]}>{totalPros}</Text>
                      <Text style={styles.miniCellLabel}>Pros</Text>
                    </View>
                    <View style={[styles.miniCell, { backgroundColor: '#FEF2F2' }]}>
                      <Ionicons name="thumbs-down" size={12} color="#DC2626" />
                      <Text style={[styles.miniCellNum, { color: '#DC2626' }]}>{totalCons}</Text>
                      <Text style={styles.miniCellLabel}>Cons</Text>
                    </View>
                    <View style={[styles.miniCell, { backgroundColor: '#EEF2FF' }]}>
                      <Ionicons name="git-compare" size={12} color="#6366F1" />
                      <Text style={[styles.miniCellNum, { color: '#6366F1' }]}>{(p.options || []).length}</Text>
                      <Text style={styles.miniCellLabel}>Opts</Text>
                    </View>
                    <View style={[styles.miniCell, { backgroundColor: '#FFFBEB' }]}>
                      <Ionicons name="list" size={12} color="#D97706" />
                      <Text style={[styles.miniCellNum, { color: '#D97706' }]}>{(p.factors || []).length}</Text>
                      <Text style={styles.miniCellLabel}>Factors</Text>
                    </View>
                  </View>

                  <View style={styles.listCardFooter}>
                    <Text style={styles.listCardDate}>
                      {new Date(p.updated_at || p.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </Text>
                    <Text style={styles.stepIndicator}>Step {p.current_step || 1}/8</Text>
                    {lifeMeta ? (
                      <View style={styles.lifeChip}>
                        <Ionicons name={lifeMeta.icon as any} size={10} color={COLORS.textSecondary} />
                        <Text style={styles.lifeChipText}>{lifeMeta.short}</Text>
                      </View>
                    ) : null}
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity
                      style={styles.deleteBtn}
                      onPress={(e) => { e.stopPropagation(); handleDelete(p.id); }}
                      hitSlop={10}
                    >
                      <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                    </TouchableOpacity>
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      )}

      {/* Create Modal */}
      <Modal visible={showCreateModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={{ width: '100%', alignItems: 'center' }}
          >
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>New Pros & Cons</Text>
                <TouchableOpacity onPress={() => setShowCreateModal(false)} hitSlop={10}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>

              <ScrollView
                style={styles.modalScroll}
                contentContainerStyle={{ paddingBottom: 8 }}
                showsVerticalScrollIndicator
                keyboardShouldPersistTaps="handled"
              >
                <Text style={styles.inputLabel}>Decision / Topic *</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="e.g., Buy a house vs. rent"
                  value={newTitle}
                  onChangeText={setNewTitle}
                  autoFocus
                />

                <Text style={styles.inputLabel}>Context (optional)</Text>
                <TextInput
                  style={[styles.textInput, { height: 70 }]}
                  placeholder="Add any relevant background..."
                  value={newContext}
                  onChangeText={setNewContext}
                  multiline
                />

                <Text style={styles.inputLabel}>Life Area (optional)</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {LIFE_AREAS.map(area => (
                      <TouchableOpacity
                        key={area.key}
                        style={[styles.lifeAreaChip, newLifeArea === area.key && styles.lifeAreaChipActive]}
                        onPress={() => setNewLifeArea(newLifeArea === area.key ? '' : area.key)}
                      >
                        <Ionicons
                          name={area.icon as any}
                          size={14}
                          color={newLifeArea === area.key ? '#FFF' : COLORS.textSecondary}
                        />
                        <Text style={[styles.lifeAreaChipText, newLifeArea === area.key && { color: '#FFF' }]}>
                          {area.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              </ScrollView>

              <View style={styles.modalFooter}>
                <TouchableOpacity
                  style={[styles.createConfirmBtn, (!newTitle.trim() || creating) && { opacity: 0.5 }]}
                  onPress={handleCreate}
                  disabled={!newTitle.trim() || creating}
                >
                  {creating ? (
                    <ActivityIndicator color="#FFF" size="small" />
                  ) : (
                    <Text style={styles.createConfirmText}>Create & Start Wizard</Text>
                  )}
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
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  header: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingTop: 12, paddingBottom: 20, gap: 12,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.85)', marginTop: 2 },
  createBtnHeader: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: '#FFF',
    justifyContent: 'center', alignItems: 'center',
  },

  howItWorks: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    backgroundColor: '#F5F3FF', borderRadius: 12, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: '#DDD6FE',
  },
  howItWorksText: { flex: 1, fontSize: 13, color: '#6D28D9', lineHeight: 18 },

  emptyState: { alignItems: 'center', paddingVertical: 48, gap: 12 },
  emptyStateTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyStateText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  emptyCreateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#7C3AED', paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 12, marginTop: 8,
  },
  emptyCreateText: { fontSize: 15, fontWeight: '600', color: '#FFF' },

  listCard: {
    backgroundColor: '#FFF', borderRadius: 14, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB',
  },
  listCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  listCardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  listCardContext: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },

  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusBadgeText: { fontSize: 11, fontWeight: '700' },

  miniGrid: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  miniCell: {
    flex: 1, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 4,
    paddingVertical: 8, borderRadius: 8,
  },
  miniCellNum: { fontSize: 14, fontWeight: '800' },
  miniCellLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },

  listCardFooter: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  listCardDate: { fontSize: 11, color: COLORS.textMuted },
  stepIndicator: { fontSize: 11, color: '#7C3AED', fontWeight: '700' },
  lifeChip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#F9FAFB', paddingHorizontal: 6, paddingVertical: 3,
    borderRadius: 6, borderWidth: 1, borderColor: '#E5E7EB',
  },
  lifeChipText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary },
  deleteBtn: { padding: 6 },

  // Modal
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end', alignItems: 'center',
  },
  modalContent: {
    width: '100%', maxWidth: 500,
    backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24,
    paddingHorizontal: 24, paddingTop: 24, paddingBottom: 0,
    maxHeight: '85%', overflow: 'hidden',
  },
  modalScroll: { flexGrow: 0, flexShrink: 1 },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 20,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  modalFooter: {
    paddingTop: 12, paddingBottom: 20,
    borderTopWidth: 1, borderTopColor: '#F1F5F9',
    backgroundColor: '#FFF',
  },
  inputLabel: {
    fontSize: 13, fontWeight: '600', color: COLORS.textSecondary,
    marginBottom: 6, marginTop: 4,
  },
  textInput: {
    backgroundColor: '#F9FAFB', borderRadius: 12, padding: 14,
    fontSize: 15, color: COLORS.textPrimary, borderWidth: 1,
    borderColor: '#E5E7EB', marginBottom: 12,
  },
  lifeAreaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB',
  },
  lifeAreaChipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  lifeAreaChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  createConfirmBtn: {
    backgroundColor: '#7C3AED', borderRadius: 14,
    paddingVertical: 16, alignItems: 'center',
  },
  createConfirmText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
