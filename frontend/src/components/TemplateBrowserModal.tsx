import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

interface TemplateBrowserModalProps {
  visible: boolean;
  onClose: () => void;
  onUseTemplate: (newDecisionId: string) => void;
  userRole?: string;
}

interface Template {
  id: string;
  name: string;
  template_type: string;
  created_by_name: string;
  source_decision_title: string;
  context: string;
  factors: any[];
  options: any[];
  created_at: string;
}

export default function TemplateBrowserModal({
  visible,
  onClose,
  onUseTemplate,
  userRole = 'user',
}: TemplateBrowserModalProps) {
  const [templates, setTemplates] = useState<{ my: Template[]; shared: Template[]; public: Template[]; authorized: Template[] }>({
    my: [], shared: [], public: [], authorized: [],
  });
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [activeTab, setActiveTab] = useState<'my' | 'shared' | 'public' | 'authorized'>('authorized');
  const [importing, setImporting] = useState(false);

  const isAdmin = ['admin', 'co_admin', 'super_admin'].includes(userRole);

  useEffect(() => {
    if (visible) {
      fetchTemplates();
    }
  }, [visible]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await api.get('/templates');
      setTemplates({
        my: response.data.my_templates || [],
        shared: response.data.shared_templates || [],
        public: response.data.public_templates || [],
        authorized: response.data.authorized_templates || [],
      });
    } catch (err: any) {
      console.error('Failed to fetch templates:', err);
    } finally {
      setLoading(false);
    }
  };

  const getTimestampWithTime = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  };

  const handleSelectTemplate = (template: Template) => {
    setSelectedTemplate(template);
    setNewTitle(`${getTimestampWithTime()} ${template.name}`);
  };

  const handleUseTemplate = async () => {
    if (!selectedTemplate || !newTitle.trim()) {
      Alert.alert('Error', 'Please enter a title for the new decision');
      return;
    }

    setCreating(true);
    try {
      const response = await api.post(`/templates/${selectedTemplate.id}/use`, {
        title: newTitle.trim(),
      });
      onUseTemplate(response.data.id);
      onClose();
      Alert.alert('Created!', 'New decision created from template');
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to create from template');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteTemplate = (template: Template) => {
    Alert.alert(
      'Delete Template',
      `Delete "${template.name}"? This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/templates/${template.id}`);
              fetchTemplates();
              if (selectedTemplate?.id === template.id) {
                setSelectedTemplate(null);
              }
            } catch (err: any) {
              Alert.alert('Error', err.response?.data?.detail || 'Failed to delete template');
            }
          },
        },
      ]
    );
  };

  const handleImportTemplate = async (template: Template) => {
    setImporting(true);
    try {
      await api.post(`/templates/${template.id}/import`);
      Alert.alert('Imported!', 'Template has been copied to your collection');
      fetchTemplates();
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to import template');
    } finally {
      setImporting(false);
    }
  };

  const handleQuickUseTemplate = async (template: Template) => {
    const defaultTitle = `${getTimestampWithTime()} ${template.name}`;
    setSelectedTemplate(template);
    setNewTitle(defaultTitle);
    // Jump straight to detail view for confirmation + create
  };

  const handleApproveTemplate = async (template: Template) => {
    try {
      await api.post(`/admin/templates/${template.id}/approve`);
      Alert.alert('Authorized!', 'Template is now in Authorized Templates');
      fetchTemplates();
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to authorize template');
    }
  };

  const handleRevokeTemplate = async (template: Template) => {
    Alert.alert(
      'Revoke Authorization',
      `Remove "${template.name}" from Authorized Templates?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revoke',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post(`/admin/templates/${template.id}/revoke`);
              Alert.alert('Revoked', 'Template moved back to Public');
              fetchTemplates();
            } catch (err: any) {
              Alert.alert('Error', err.response?.data?.detail || 'Failed to revoke');
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const datePart = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const timePart = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    return `${datePart} ${timePart}`;
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>
              {selectedTemplate ? 'Use Template' : 'Template Library'}
            </Text>
            <TouchableOpacity
              onPress={() => {
                if (selectedTemplate) {
                  setSelectedTemplate(null);
                } else {
                  onClose();
                }
              }}
              style={styles.closeBtn}
            >
              <Ionicons
                name={selectedTemplate ? 'arrow-back' : 'close'}
                size={24}
                color={COLORS.textSecondary}
              />
            </TouchableOpacity>
          </View>

          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={COLORS.primary} />
              <Text style={styles.loadingText}>Loading templates...</Text>
            </View>
          ) : selectedTemplate ? (
            /* Template Detail & Use */
            <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
              <View style={styles.templateDetail}>
                <View style={styles.templateDetailHeader}>
                  <View style={[
                    styles.typeBadge,
                    selectedTemplate.template_type === 'assessment' ? styles.typeBadgeAssessment : styles.typeBadgeOptions,
                  ]}>
                    <Ionicons
                      name={selectedTemplate.template_type === 'assessment' ? 'analytics-outline' : 'layers-outline'}
                      size={14}
                      color={selectedTemplate.template_type === 'assessment' ? '#10B981' : '#F59E0B'}
                    />
                    <Text style={[
                      styles.typeBadgeText,
                      { color: selectedTemplate.template_type === 'assessment' ? '#10B981' : '#F59E0B' },
                    ]}>
                      {selectedTemplate.template_type === 'assessment' ? 'With Assessment' : 'With Options'}
                    </Text>
                  </View>
                </View>

                <Text style={styles.detailName}>{selectedTemplate.name}</Text>
                <Text style={styles.detailMeta}>
                  By {selectedTemplate.created_by_name} • {formatDate(selectedTemplate.created_at)}
                </Text>

                {selectedTemplate.context ? (
                  <View style={styles.detailSection}>
                    <Text style={styles.detailSectionTitle}>Context</Text>
                    <Text style={styles.detailText} numberOfLines={3}>
                      {selectedTemplate.context}
                    </Text>
                  </View>
                ) : null}

                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>
                    Factors ({selectedTemplate.factors?.length || 0})
                  </Text>
                  {selectedTemplate.factors?.slice(0, 5).map((f: any, i: number) => (
                    <View key={i} style={styles.factorItem}>
                      <View style={[
                        styles.factorDot,
                        { backgroundColor: f.category === 'primary' ? COLORS.primary : COLORS.textMuted },
                      ]} />
                      <Text style={styles.factorItemText}>{f.name}</Text>
                      <Text style={styles.factorItemRating}>{f.rating}</Text>
                    </View>
                  ))}
                  {(selectedTemplate.factors?.length || 0) > 5 && (
                    <Text style={styles.moreText}>
                      +{(selectedTemplate.factors?.length || 0) - 5} more
                    </Text>
                  )}
                </View>

                {selectedTemplate.options?.length > 0 && (
                  <View style={styles.detailSection}>
                    <Text style={styles.detailSectionTitle}>
                      Options ({selectedTemplate.options.length})
                    </Text>
                    {selectedTemplate.options.map((opt: any, i: number) => (
                      <View key={i} style={styles.optionItem}>
                        <Ionicons name="ellipse-outline" size={14} color={COLORS.textMuted} />
                        <Text style={styles.optionItemText}>{opt.name}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>

              {/* Title Input */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>New Decision Title</Text>
                <TextInput
                  style={styles.input}
                  value={newTitle}
                  onChangeText={setNewTitle}
                  placeholder="Enter title for new decision..."
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>
            </ScrollView>
          ) : (
            /* Template List with 3 tabs */
            <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
              {/* Tab switcher */}
              <View style={styles.tabRow}>
                {(['authorized', 'my', 'shared', 'public'] as const).map((tab) => {
                  const count = templates[tab].length;
                  const labels = { authorized: 'Authorized', my: 'Mine', shared: 'Shared', public: 'Public' };
                  const icons = { authorized: 'shield-checkmark-outline', my: 'person-outline', shared: 'people-outline', public: 'globe-outline' } as const;
                  return (
                    <TouchableOpacity
                      key={tab}
                      style={[styles.tab, activeTab === tab && styles.tabActive]}
                      onPress={() => setActiveTab(tab)}
                    >
                      <Ionicons name={icons[tab]} size={14} color={activeTab === tab ? (tab === 'authorized' ? '#10B981' : COLORS.primary) : COLORS.textMuted} />
                      <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive, tab === 'authorized' && activeTab === tab && { color: '#10B981' }]}>
                        {labels[tab]}{count > 0 ? ` ${count}` : ''}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {templates[activeTab].length === 0 ? (
                <View style={styles.emptyState}>
                  <Ionicons
                    name={activeTab === 'my' ? 'bookmark-outline' : activeTab === 'shared' ? 'people-outline' : activeTab === 'authorized' ? 'shield-checkmark-outline' : 'globe-outline'}
                    size={48}
                    color={COLORS.textMuted}
                  />
                  <Text style={styles.emptyTitle}>
                    {activeTab === 'my' ? 'No Templates Yet' : activeTab === 'shared' ? 'No Shared Templates' : activeTab === 'authorized' ? 'No Authorized Templates' : 'No Public Templates'}
                  </Text>
                  <Text style={styles.emptyText}>
                    {activeTab === 'my'
                      ? 'Save a decision as a template from the Clone menu.'
                      : activeTab === 'shared'
                      ? 'No one has shared a template with your account yet.'
                      : activeTab === 'authorized'
                      ? 'No admin-approved templates available yet.'
                      : 'No public templates available.'}
                  </Text>
                </View>
              ) : (
                templates[activeTab].map((template) => (
                  <TouchableOpacity
                    key={template.id}
                    style={styles.templateCard}
                    onPress={() => handleSelectTemplate(template)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.templateCardHeader}>
                      <View style={[
                        styles.typeBadge,
                        template.template_type === 'assessment' ? styles.typeBadgeAssessment : styles.typeBadgeOptions,
                      ]}>
                        <Ionicons
                          name={template.template_type === 'assessment' ? 'analytics-outline' : 'layers-outline'}
                          size={12}
                          color={template.template_type === 'assessment' ? '#10B981' : '#F59E0B'}
                        />
                        <Text style={[
                          styles.typeBadgeText,
                          { color: template.template_type === 'assessment' ? '#10B981' : '#F59E0B' },
                        ]}>
                          {template.template_type === 'assessment' ? 'Assessment' : 'Options'}
                        </Text>
                      </View>
                      <View style={styles.templateCardActions}>
                        {/* Use template button for shared/public/authorized templates */}
                        {activeTab !== 'my' && (
                          <>
                            <TouchableOpacity
                              onPress={(e) => {
                                e.stopPropagation?.();
                                handleQuickUseTemplate(template);
                              }}
                              style={styles.useBtn}
                            >
                              <Ionicons name="add-circle-outline" size={14} color="#FFF" />
                              <Text style={styles.useBtnText}>Use</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                              onPress={(e) => {
                                e.stopPropagation?.();
                                handleImportTemplate(template);
                              }}
                              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                              disabled={importing}
                              style={styles.saveMineBtn}
                            >
                              <Ionicons name="bookmark-outline" size={16} color={COLORS.primary} />
                            </TouchableOpacity>
                          </>
                        )}
                        {/* Admin: Approve button on public templates */}
                        {isAdmin && activeTab === 'public' && (
                          <TouchableOpacity
                            onPress={(e) => {
                              e.stopPropagation?.();
                              handleApproveTemplate(template);
                            }}
                            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                            style={styles.approveBtn}
                          >
                            <Ionicons name="shield-checkmark-outline" size={14} color="#10B981" />
                            <Text style={styles.approveBtnText}>Approve</Text>
                          </TouchableOpacity>
                        )}
                        {/* Admin: Revoke button on authorized templates */}
                        {isAdmin && activeTab === 'authorized' && (
                          <TouchableOpacity
                            onPress={(e) => {
                              e.stopPropagation?.();
                              handleRevokeTemplate(template);
                            }}
                            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                            style={styles.revokeBtn}
                          >
                            <Ionicons name="close-circle-outline" size={14} color={COLORS.error} />
                            <Text style={styles.revokeBtnText}>Revoke</Text>
                          </TouchableOpacity>
                        )}
                        {/* Delete button for own templates */}
                        {activeTab === 'my' && (
                          <TouchableOpacity
                            onPress={(e) => {
                              e.stopPropagation?.();
                              handleDeleteTemplate(template);
                            }}
                            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                          >
                            <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
                          </TouchableOpacity>
                        )}
                      </View>
                    </View>
                    <Text style={styles.templateName} numberOfLines={1}>{template.name}</Text>
                    <Text style={styles.templateMeta}>
                      {template.factors?.length || 0} factors • {template.options?.length || 0} options
                    </Text>
                    <Text style={styles.templateAuthor}>
                      By {template.created_by_name} • {formatDate(template.created_at)}
                    </Text>
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
          )}

          {/* Footer Action */}
          {selectedTemplate && (
            <View style={styles.footer}>
              <TouchableOpacity
                style={[styles.actionBtn, creating && styles.actionBtnDisabled]}
                onPress={handleUseTemplate}
                disabled={creating}
              >
                {creating ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="add-circle" size={20} color="#FFF" />
                    <Text style={styles.actionBtnText}>Create Decision</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: COLORS.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '85%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingBottom: 12,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  closeBtn: {
    padding: 4,
  },
  body: {
    paddingHorizontal: 20,
    maxHeight: 500,
  },
  loadingContainer: {
    padding: 40,
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
    color: COLORS.textMuted,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
    gap: 8,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  emptyText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  templateCard: {
    backgroundColor: COLORS.background,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  templateCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  templateCardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  importBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  importBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  useBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
  },
  useBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFF',
  },
  saveMineBtn: {
    padding: 4,
  },
  approveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  approveBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#10B981',
  },
  revokeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  revokeBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.error,
  },
  tabRow: {
    flexDirection: 'row',
    backgroundColor: COLORS.background,
    borderRadius: 10,
    padding: 3,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    borderRadius: 8,
    gap: 4,
  },
  tabActive: {
    backgroundColor: COLORS.white,
    elevation: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
  },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  tabTextActive: {
    color: COLORS.primary,
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    gap: 4,
  },
  typeBadgeOptions: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
  },
  typeBadgeAssessment: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  templateName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  templateMeta: {
    fontSize: 13,
    color: COLORS.textSecondary,
    marginBottom: 2,
  },
  templateAuthor: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  // Template Detail
  templateDetail: {
    marginBottom: 16,
  },
  templateDetailHeader: {
    marginBottom: 12,
  },
  detailName: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  detailMeta: {
    fontSize: 13,
    color: COLORS.textMuted,
    marginBottom: 16,
  },
  detailSection: {
    marginBottom: 14,
  },
  detailSectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  detailText: {
    fontSize: 14,
    color: COLORS.textPrimary,
    lineHeight: 20,
  },
  factorItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 4,
  },
  factorDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  factorItemText: {
    fontSize: 14,
    color: COLORS.textPrimary,
    flex: 1,
  },
  factorItemRating: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  moreText: {
    fontSize: 12,
    color: COLORS.textMuted,
    fontStyle: 'italic',
    paddingLeft: 16,
    paddingTop: 2,
  },
  optionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 3,
  },
  optionItemText: {
    fontSize: 14,
    color: COLORS.textPrimary,
  },
  inputSection: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: COLORS.background,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 15,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  footer: {
    padding: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.primary,
    borderRadius: 14,
    paddingVertical: 14,
    gap: 8,
  },
  actionBtnDisabled: {
    opacity: 0.7,
  },
  actionBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
});
