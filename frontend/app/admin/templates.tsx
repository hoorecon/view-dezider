import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

interface Template {
  id: string;
  name: string;
  life_area: string;
  decision_type: string;
  description?: string;
  factors: any[];
  is_approved: boolean;
  created_by?: string;
  created_at?: string;
}

export default function AdminTemplates() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all');
  const [editModal, setEditModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [form, setForm] = useState({ name: '', life_area: '', decision_type: '', description: '' });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/decision-templates/all');
      setTemplates(resp.data || []);
    } catch (err) {
      Alert.alert('Error', 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (templateId: string) => {
    try {
      await api.post(`/decision-templates/${templateId}/approve`);
      setTemplates(templates.map(t => t.id === templateId ? { ...t, is_approved: true } : t));
      Alert.alert('Success', 'Template approved');
    } catch (err) {
      Alert.alert('Error', 'Failed to approve template');
    }
  };

  const handleDelete = async (templateId: string) => {
    Alert.alert('Delete Template', 'Are you sure you want to delete this template?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/decision-templates/${templateId}`);
            setTemplates(templates.filter(t => t.id !== templateId));
          } catch (err) {
            Alert.alert('Error', 'Failed to delete template');
          }
        },
      },
    ]);
  };

  const openEdit = (template: Template) => {
    setEditingTemplate(template);
    setForm({
      name: template.name,
      life_area: template.life_area || '',
      decision_type: template.decision_type || '',
      description: template.description || '',
    });
    setEditModal(true);
  };

  const handleSaveEdit = async () => {
    if (!editingTemplate) return;
    try {
      await api.put(`/decision-templates/${editingTemplate.id}`, {
        ...form,
        factors: editingTemplate.factors,
      });
      setTemplates(templates.map(t => t.id === editingTemplate.id ? { ...t, ...form } : t));
      setEditModal(false);
      Alert.alert('Success', 'Template updated');
    } catch (err) {
      Alert.alert('Error', 'Failed to update template');
    }
  };

  const filteredTemplates = templates.filter(t => {
    if (filter === 'pending') return !t.is_approved;
    if (filter === 'approved') return t.is_approved;
    return true;
  });

  const pendingCount = templates.filter(t => !t.is_approved).length;

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Template Management</Text>
          <Text style={styles.subtitle}>{templates.length} templates · {pendingCount} pending</Text>
        </View>
        <TouchableOpacity onPress={fetchTemplates} style={styles.refreshBtn}>
          <Ionicons name="refresh" size={20} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      {/* Filter tabs */}
      <View style={styles.filterRow}>
        {(['all', 'pending', 'approved'] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterTab, filter === f && styles.filterTabActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterTabText, filter === f && styles.filterTabTextActive]}>
              {f === 'all' ? 'All' : f === 'pending' ? `Pending (${pendingCount})` : 'Approved'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.list}>
          {filteredTemplates.length === 0 && (
            <View style={styles.emptyState}>
              <Ionicons name="document-text-outline" size={48} color={COLORS.textMuted} />
              <Text style={styles.emptyText}>No templates found</Text>
            </View>
          )}

          {filteredTemplates.map((template) => (
            <View key={template.id} style={[styles.card, !template.is_approved && styles.cardPending]}>
              <View style={styles.cardHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>{template.name}</Text>
                  <View style={styles.cardMeta}>
                    {template.life_area ? (
                      <View style={styles.metaBadge}>
                        <Text style={styles.metaBadgeText}>{template.life_area}</Text>
                      </View>
                    ) : null}
                    {template.decision_type ? (
                      <View style={[styles.metaBadge, { backgroundColor: '#EDE9FE' }]}>
                        <Text style={[styles.metaBadgeText, { color: COLORS.primary }]}>{template.decision_type}</Text>
                      </View>
                    ) : null}
                    <Text style={styles.factorCount}>{template.factors?.length || 0} factors</Text>
                  </View>
                </View>
                <View style={[styles.statusBadge, template.is_approved ? styles.statusApproved : styles.statusPending]}>
                  <Ionicons
                    name={template.is_approved ? 'checkmark-circle' : 'time'}
                    size={14}
                    color={template.is_approved ? '#16A34A' : '#F59E0B'}
                  />
                  <Text style={[styles.statusText, template.is_approved ? { color: '#16A34A' } : { color: '#F59E0B' }]}>
                    {template.is_approved ? 'Approved' : 'Pending'}
                  </Text>
                </View>
              </View>

              {template.description ? (
                <Text style={styles.cardDesc} numberOfLines={2}>{template.description}</Text>
              ) : null}

              {/* Factor preview */}
              {template.factors && template.factors.length > 0 && (
                <View style={styles.factorPreview}>
                  {template.factors.slice(0, 5).map((f: any, idx: number) => (
                    <View key={idx} style={styles.factorChip}>
                      <Text style={styles.factorChipText}>{f.name}</Text>
                    </View>
                  ))}
                  {template.factors.length > 5 && (
                    <Text style={styles.moreText}>+{template.factors.length - 5} more</Text>
                  )}
                </View>
              )}

              {/* Actions */}
              <View style={styles.cardActions}>
                {!template.is_approved && (
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.actionApprove]}
                    onPress={() => handleApprove(template.id)}
                  >
                    <Ionicons name="checkmark" size={16} color="#FFF" />
                    <Text style={styles.actionBtnText}>Approve</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={[styles.actionBtn, styles.actionEdit]}
                  onPress={() => openEdit(template)}
                >
                  <Ionicons name="create-outline" size={16} color={COLORS.primary} />
                  <Text style={[styles.actionBtnText, { color: COLORS.primary }]}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.actionBtn, styles.actionDelete]}
                  onPress={() => handleDelete(template.id)}
                >
                  <Ionicons name="trash-outline" size={16} color="#EF4444" />
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {/* Edit Modal */}
      <Modal visible={editModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Template</Text>
              <TouchableOpacity onPress={() => setEditModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.fieldLabel}>Name</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.name}
                onChangeText={(t) => setForm({ ...form, name: t })}
                placeholder="Template name"
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={styles.fieldLabel}>Life Area</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.life_area}
                onChangeText={(t) => setForm({ ...form, life_area: t })}
                placeholder="e.g., Career, Finance, Health"
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={styles.fieldLabel}>Decision Type</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.decision_type}
                onChangeText={(t) => setForm({ ...form, decision_type: t })}
                placeholder="e.g., Job Offer, Investment"
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={styles.fieldLabel}>Description</Text>
              <TextInput
                style={[styles.fieldInput, { minHeight: 80, textAlignVertical: 'top' }]}
                value={form.description}
                onChangeText={(t) => setForm({ ...form, description: t })}
                placeholder="Brief description..."
                placeholderTextColor={COLORS.textMuted}
                multiline
              />

              {editingTemplate?.factors && (
                <>
                  <Text style={styles.fieldLabel}>Factors ({editingTemplate.factors.length})</Text>
                  <View style={styles.factorPreview}>
                    {editingTemplate.factors.map((f: any, idx: number) => (
                      <View key={idx} style={styles.factorChip}>
                        <Text style={styles.factorChipText}>{f.name}</Text>
                        <Text style={styles.factorChipMeta}>{f.category}</Text>
                      </View>
                    ))}
                  </View>
                </>
              )}
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setEditModal(false)}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSaveEdit}>
                <Text style={styles.saveBtnText}>Save Changes</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  backBtn: { padding: 4 },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textMuted },
  refreshBtn: { padding: 8, backgroundColor: '#F5F3FF', borderRadius: 8 },
  filterRow: { flexDirection: 'row', padding: 12, gap: 8 },
  filterTab: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: '#F1F5F9' },
  filterTabActive: { backgroundColor: COLORS.primary },
  filterTabText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  filterTabTextActive: { color: '#FFF' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  list: { padding: 12, gap: 12, paddingBottom: 32 },
  emptyState: { alignItems: 'center', paddingVertical: 48, gap: 12 },
  emptyText: { fontSize: 16, color: COLORS.textMuted },
  card: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  cardPending: { borderLeftWidth: 3, borderLeftColor: '#F59E0B' },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  metaBadge: { backgroundColor: '#DBEAFE', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  metaBadgeText: { fontSize: 11, fontWeight: '600', color: '#3B82F6' },
  factorCount: { fontSize: 11, color: COLORS.textMuted },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  statusApproved: { backgroundColor: '#DCFCE7' },
  statusPending: { backgroundColor: '#FEF3C7' },
  statusText: { fontSize: 11, fontWeight: '600' },
  cardDesc: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 8 },
  factorPreview: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 8 },
  factorChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F1F5F9', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  factorChipText: { fontSize: 11, color: COLORS.textPrimary, fontWeight: '500' },
  factorChipMeta: { fontSize: 9, color: COLORS.textMuted },
  moreText: { fontSize: 11, color: COLORS.textMuted, alignSelf: 'center' },
  cardActions: { flexDirection: 'row', gap: 8, borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 8 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  actionApprove: { backgroundColor: '#16A34A' },
  actionEdit: { backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: COLORS.primary },
  actionDelete: { backgroundColor: '#FEE2E2', marginLeft: 'auto' },
  actionBtnText: { fontSize: 12, fontWeight: '600', color: '#FFF' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  modalBody: { padding: 16, maxHeight: 400 },
  modalFooter: { flexDirection: 'row', padding: 16, gap: 12, borderTopWidth: 1, borderTopColor: COLORS.border },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted, marginTop: 12, marginBottom: 4 },
  fieldInput: { height: 42, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, fontSize: 14, color: COLORS.textPrimary, backgroundColor: '#FAFAFA' },
  cancelBtn: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 10, backgroundColor: '#F1F5F9' },
  cancelBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary },
  saveBtn: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 10, backgroundColor: COLORS.primary },
  saveBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
