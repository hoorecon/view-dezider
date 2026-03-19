import React, { useState } from 'react';
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

interface CloneTemplateModalProps {
  visible: boolean;
  onClose: () => void;
  decision: any;
  onCloneSuccess: (newId: string) => void;
  onTemplateSuccess?: () => void;
}

const CLONE_LEVELS = [
  {
    key: 'factors',
    label: 'Copy Factors',
    icon: 'list-outline' as const,
    description: 'Factor names only — start fresh with classification',
    color: '#3B82F6',
  },
  {
    key: 'classification',
    label: 'Copy Classification',
    icon: 'git-branch-outline' as const,
    description: 'Factors + Primary/Secondary classification',
    color: '#8B5CF6',
  },
  {
    key: 'prioritization',
    label: 'Copy Prioritization',
    icon: 'bar-chart-outline' as const,
    description: 'Factors + Classification + Ratings',
    color: '#EC4899',
  },
  {
    key: 'options',
    label: 'Copy Options',
    icon: 'layers-outline' as const,
    description: 'All above + Option names (no assessments)',
    color: '#F59E0B',
  },
  {
    key: 'assessment',
    label: 'Copy Assessment',
    icon: 'copy-outline' as const,
    description: 'Full clone — everything including assessments',
    color: '#10B981',
  },
];

const TEMPLATE_TYPES = [
  {
    key: 'options',
    label: 'With Options',
    icon: 'layers-outline' as const,
    description: 'Factors prioritized + Options listed (no assessments)',
    color: '#F59E0B',
  },
  {
    key: 'assessment',
    label: 'With Assessment',
    icon: 'analytics-outline' as const,
    description: 'Full template including all assessments',
    color: '#10B981',
  },
];

type Tab = 'clone' | 'template';

export default function CloneTemplateModal({
  visible,
  onClose,
  decision,
  onCloneSuccess,
  onTemplateSuccess,
}: CloneTemplateModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>('clone');
  const [selectedCloneLevel, setSelectedCloneLevel] = useState('prioritization');
  const [selectedTemplateType, setSelectedTemplateType] = useState('options');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);

  const getTimestampPrefix = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  };

  const getDefaultTitle = () => {
    if (activeTab === 'clone') {
      return `${getTimestampPrefix()} ${decision?.title || 'Decision'}`;
    }
    return `${getTimestampPrefix()} ${decision?.title || 'Template'}`;
  };

  React.useEffect(() => {
    if (visible) {
      setTitle(getDefaultTitle());
    }
  }, [visible, activeTab]);

  const handleClone = async () => {
    if (!title.trim()) {
      Alert.alert('Error', 'Please enter a title for the cloned decision');
      return;
    }
    
    setLoading(true);
    try {
      const response = await api.post(`/decisions/${decision.id}/clone`, {
        title: title.trim(),
        clone_level: selectedCloneLevel,
      });
      onCloneSuccess(response.data.id);
      onClose();
      Alert.alert('Cloned!', `Decision cloned with "${CLONE_LEVELS.find(l => l.key === selectedCloneLevel)?.label}"`);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to clone decision');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTemplate = async () => {
    if (!title.trim()) {
      Alert.alert('Error', 'Please enter a name for the template');
      return;
    }
    
    setLoading(true);
    try {
      await api.post(`/decisions/${decision.id}/save-as-template`, {
        name: title.trim(),
        template_type: selectedTemplateType,
      });
      onTemplateSuccess?.();
      onClose();
      Alert.alert('Saved!', 'Template saved and shared across all users');
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>
              {activeTab === 'clone' ? 'Clone Decision' : 'Save as Template'}
            </Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Ionicons name="close" size={24} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {/* Tab Switcher */}
          <View style={styles.tabRow}>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'clone' && styles.tabActive]}
              onPress={() => setActiveTab('clone')}
            >
              <Ionicons name="copy-outline" size={18} color={activeTab === 'clone' ? COLORS.primary : COLORS.textMuted} />
              <Text style={[styles.tabText, activeTab === 'clone' && styles.tabTextActive]}>Clone</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'template' && styles.tabActive]}
              onPress={() => setActiveTab('template')}
            >
              <Ionicons name="bookmark-outline" size={18} color={activeTab === 'template' ? COLORS.primary : COLORS.textMuted} />
              <Text style={[styles.tabText, activeTab === 'template' && styles.tabTextActive]}>Template</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Source decision info */}
            <View style={styles.sourceInfo}>
              <Ionicons name="document-text-outline" size={16} color={COLORS.textMuted} />
              <Text style={styles.sourceText} numberOfLines={1}>
                From: {decision?.title}
              </Text>
            </View>

            {/* Title Input */}
            <View style={styles.inputSection}>
              <Text style={styles.inputLabel}>
                {activeTab === 'clone' ? 'New Decision Title' : 'Template Name'}
              </Text>
              <TextInput
                style={styles.input}
                value={title}
                onChangeText={setTitle}
                placeholder={activeTab === 'clone' ? 'Enter decision title...' : 'Enter template name...'}
                placeholderTextColor={COLORS.textMuted}
              />
            </View>

            {/* Clone Levels / Template Types */}
            {activeTab === 'clone' ? (
              <View style={styles.optionsSection}>
                <Text style={styles.sectionLabel}>What to copy?</Text>
                {CLONE_LEVELS.map((level) => (
                  <TouchableOpacity
                    key={level.key}
                    style={[
                      styles.optionCard,
                      selectedCloneLevel === level.key && styles.optionCardSelected,
                      selectedCloneLevel === level.key && { borderColor: level.color },
                    ]}
                    onPress={() => setSelectedCloneLevel(level.key)}
                  >
                    <View style={[styles.optionIcon, { backgroundColor: `${level.color}15` }]}>
                      <Ionicons name={level.icon} size={20} color={level.color} />
                    </View>
                    <View style={styles.optionInfo}>
                      <Text style={styles.optionLabel}>{level.label}</Text>
                      <Text style={styles.optionDesc}>{level.description}</Text>
                    </View>
                    <View style={[
                      styles.radio,
                      selectedCloneLevel === level.key && { borderColor: level.color, backgroundColor: level.color },
                    ]}>
                      {selectedCloneLevel === level.key && (
                        <Ionicons name="checkmark" size={14} color="#FFF" />
                      )}
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={styles.optionsSection}>
                <Text style={styles.sectionLabel}>Template type</Text>
                <Text style={styles.sectionSubLabel}>
                  Templates are shared across all app users
                </Text>
                {TEMPLATE_TYPES.map((type) => (
                  <TouchableOpacity
                    key={type.key}
                    style={[
                      styles.optionCard,
                      selectedTemplateType === type.key && styles.optionCardSelected,
                      selectedTemplateType === type.key && { borderColor: type.color },
                    ]}
                    onPress={() => setSelectedTemplateType(type.key)}
                  >
                    <View style={[styles.optionIcon, { backgroundColor: `${type.color}15` }]}>
                      <Ionicons name={type.icon} size={20} color={type.color} />
                    </View>
                    <View style={styles.optionInfo}>
                      <Text style={styles.optionLabel}>{type.label}</Text>
                      <Text style={styles.optionDesc}>{type.description}</Text>
                    </View>
                    <View style={[
                      styles.radio,
                      selectedTemplateType === type.key && { borderColor: type.color, backgroundColor: type.color },
                    ]}>
                      {selectedTemplateType === type.key && (
                        <Ionicons name="checkmark" size={14} color="#FFF" />
                      )}
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </ScrollView>

          {/* Action Button */}
          <View style={styles.footer}>
            <TouchableOpacity
              style={[styles.actionBtn, loading && styles.actionBtnDisabled]}
              onPress={activeTab === 'clone' ? handleClone : handleSaveTemplate}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <Ionicons
                    name={activeTab === 'clone' ? 'copy' : 'bookmark'}
                    size={20}
                    color="#FFF"
                  />
                  <Text style={styles.actionBtnText}>
                    {activeTab === 'clone' ? 'Clone Decision' : 'Save Template'}
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>
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
    maxHeight: '90%',
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
  tabRow: {
    flexDirection: 'row',
    marginHorizontal: 20,
    backgroundColor: COLORS.background,
    borderRadius: 12,
    padding: 4,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  tabActive: {
    backgroundColor: COLORS.white,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  tabTextActive: {
    color: COLORS.primary,
  },
  body: {
    paddingHorizontal: 20,
    maxHeight: 450,
  },
  sourceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: COLORS.background,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginBottom: 16,
  },
  sourceText: {
    fontSize: 13,
    color: COLORS.textSecondary,
    flex: 1,
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
  optionsSection: {
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  sectionSubLabel: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginBottom: 12,
    fontStyle: 'italic',
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    marginBottom: 8,
    gap: 12,
  },
  optionCardSelected: {
    backgroundColor: 'rgba(142, 36, 170, 0.04)',
  },
  optionIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionInfo: {
    flex: 1,
  },
  optionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  optionDesc: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
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
