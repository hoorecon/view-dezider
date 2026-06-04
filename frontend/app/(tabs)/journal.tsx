import React, { useState, useCallback, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

interface JournalEntry {
  id: string;
  decision_title: string;
  decision_description: string;
  linked_module?: string;
  linked_id?: string;
  linked_title?: string;
  entry_type?: string;
  outcome: string;
  outcome_rating: number;
  lessons_learned: string;
  failure_reasons: string[];
  status: string;
  decision_date: string;
  created_at: string;
}

interface LinkableItem {
  id: string;
  title: string;
  extra: string;
}

interface Reminder {
  decision_id: string;
  title: string;
  decision_type: string;
  life_area: string;
  priority_label: string;
  implementation_review_date: string;
  status: string;
}

const MODULE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  decision: { label: 'My Dezider', icon: 'compass', color: '#8E24AA' },
  pros_cons: { label: 'Pros & Cons', icon: 'git-compare', color: '#6366F1' },
  swot: { label: 'SWOT', icon: 'grid', color: '#E91E63' },
  solution_finder: { label: 'Solution Finder', icon: 'search', color: '#0097A7' },
  gem: { label: 'GEM Goal', icon: 'flag', color: '#F59E0B' },
  ctt: { label: 'CTT Task', icon: 'checkmark-circle', color: '#3B82F6' },
  lifestyle: { label: 'Lifestyle Routine', icon: 'leaf', color: '#10B981' },
};

const ENTRY_TYPES = [
  { key: 'best_practice', label: 'Best Practice', icon: 'trophy', color: '#10B981', desc: 'Went well — worth repeating' },
  { key: 'learning', label: 'Learning', icon: 'school', color: '#EF4444', desc: "Didn't go as planned — lesson learned" },
];

const FAILURE_REASONS = [
  'Missed important factors',
  'Underestimated factor importance',
  'Unrealistic assessment',
  'Insufficient options considered',
  'Delayed implementation',
];

export default function JournalScreen() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);
  const [saving, setSaving] = useState(false);
  const [activeFilter, setActiveFilter] = useState<string>('all');

  // Create form state
  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formEntryType, setFormEntryType] = useState<string>('');
  const [formLinkedModule, setFormLinkedModule] = useState<string>('');
  const [formLinkedId, setFormLinkedId] = useState<string>('');
  const [formLinkedTitle, setFormLinkedTitle] = useState<string>('');
  const [linkableItems, setLinkableItems] = useState<Record<string, LinkableItem[]>>({});
  const [showModulePicker, setShowModulePicker] = useState(false);
  const [showItemPicker, setShowItemPicker] = useState(false);
  const [loadingItems, setLoadingItems] = useState(false);

  // Detail/update form
  const [editOutcome, setEditOutcome] = useState('');
  const [editLessons, setEditLessons] = useState('');
  const [editRating, setEditRating] = useState(0);
  const [editFailureReasons, setEditFailureReasons] = useState<string[]>([]);
  const [editStatus, setEditStatus] = useState('');
  const [updatingEntry, setUpdatingEntry] = useState(false);

  const fetchEntries = async () => {
    try {
      const query = activeFilter !== 'all' ? `?linked_module=${activeFilter}` : '';
      const response = await api.get(`/journal${query}`);
      setEntries(response.data);
    } catch (error) {
      console.error('Error fetching entries:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchReminders = async () => {
    try {
      const response = await api.get('/journal/reminders');
      setReminders(response.data || []);
    } catch (error) {
      console.error('Error fetching reminders:', error);
    }
  };

  const fetchLinkableItems = async () => {
    setLoadingItems(true);
    try {
      const response = await api.get('/journal/linkable-items');
      setLinkableItems(response.data);
    } catch (error) {
      console.error('Error fetching linkable items:', error);
    } finally {
      setLoadingItems(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchEntries();
      fetchReminders();
    }, [activeFilter])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchEntries(), fetchReminders()]);
    setRefreshing(false);
  };

  const resetForm = () => {
    setFormTitle('');
    setFormDescription('');
    setFormEntryType('');
    setFormLinkedModule('');
    setFormLinkedId('');
    setFormLinkedTitle('');
  };

  const openCreateModal = (presetModule?: string, presetId?: string, presetTitle?: string) => {
    resetForm();
    if (presetModule) setFormLinkedModule(presetModule);
    if (presetId) setFormLinkedId(presetId);
    if (presetTitle) {
      setFormLinkedTitle(presetTitle);
      setFormTitle(`Review: ${presetTitle}`);
    }
    fetchLinkableItems();
    setModalVisible(true);
  };

  const handleCreate = async () => {
    if (!formTitle.trim()) {
      showAlert('Error', 'Please enter a title');
      return;
    }
    if (!formLinkedModule) {
      showAlert('Link Required', 'Please link this journal entry to a module (Decision, GEM, CTT, etc.)');
      return;
    }
    if (!formEntryType) {
      showAlert('Type Required', 'Please select whether this is a Best Practice or Learning');
      return;
    }

    setSaving(true);
    try {
      await api.post('/journal', {
        decision_title: formTitle.trim(),
        decision_description: formDescription.trim(),
        linked_module: formLinkedModule,
        linked_id: formLinkedId || undefined,
        linked_title: formLinkedTitle || undefined,
        entry_type: formEntryType,
      });
      setModalVisible(false);
      resetForm();
      fetchEntries();
      fetchReminders();
    } catch (error) {
      showAlert('Error', 'Failed to create entry');
    } finally {
      setSaving(false);
    }
  };

  const openDetailModal = (entry: JournalEntry) => {
    setSelectedEntry(entry);
    setEditOutcome(entry.outcome || '');
    setEditLessons(entry.lessons_learned || '');
    setEditRating(entry.outcome_rating || 0);
    setEditFailureReasons(entry.failure_reasons || []);
    setEditStatus(entry.status || 'pending');
    setDetailModalVisible(true);
  };

  const handleUpdateEntry = async () => {
    if (!selectedEntry) return;
    setUpdatingEntry(true);
    try {
      await api.put(`/journal/${selectedEntry.id}`, {
        outcome: editOutcome,
        lessons_learned: editLessons,
        outcome_rating: editRating,
        failure_reasons: editFailureReasons,
        status: editStatus,
      });
      setDetailModalVisible(false);
      fetchEntries();
    } catch (error) {
      showAlert('Error', 'Failed to update entry');
    } finally {
      setUpdatingEntry(false);
    }
  };

  const handleDelete = async (id: string) => {
    showAlert('Delete Entry', 'Are you sure you want to delete this journal entry?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/journal/${id}`);
            setEntries(entries.filter((e) => e.id !== id));
          } catch (error) {
            showAlert('Error', 'Failed to delete entry');
          }
        },
      },
    ]);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getEntryTypeBadge = (entryType?: string) => {
    if (!entryType) return null;
    const config = ENTRY_TYPES.find((t) => t.key === entryType);
    if (!config) return null;
    return (
      <View style={[styles.typeBadge, { backgroundColor: config.color + '18' }]}>
        <Ionicons name={config.icon as any} size={12} color={config.color} />
        <Text style={[styles.typeBadgeText, { color: config.color }]}>{config.label}</Text>
      </View>
    );
  };

  const getModuleBadge = (module?: string) => {
    if (!module) return null;
    const config = MODULE_CONFIG[module];
    if (!config) return null;
    return (
      <View style={[styles.moduleBadge, { backgroundColor: config.color + '15' }]}>
        <Ionicons name={config.icon as any} size={11} color={config.color} />
        <Text style={[styles.moduleBadgeText, { color: config.color }]}>{config.label}</Text>
      </View>
    );
  };

  const renderReminderCard = ({ item }: { item: Reminder }) => {
    const isProblem = item.decision_type === 'problem';
    const bgColor = isProblem ? '#EF4444' : '#F59E0B';
    const reviewDate = new Date(item.implementation_review_date);
    const daysOverdue = Math.floor((Date.now() - reviewDate.getTime()) / (1000 * 60 * 60 * 24));

    return (
      <TouchableOpacity
        style={[styles.reminderCard, { borderLeftColor: bgColor }]}
        onPress={() => openCreateModal('decision', item.decision_id, item.title)}
        activeOpacity={0.7}
      >
        <View style={styles.reminderHeader}>
          <View style={[styles.priorityPill, { backgroundColor: bgColor + '20' }]}>
            <Text style={[styles.priorityPillText, { color: bgColor }]}>{item.priority_label}</Text>
          </View>
          {daysOverdue > 0 && (
            <Text style={styles.overdueText}>{daysOverdue}d overdue</Text>
          )}
        </View>
        <Text style={styles.reminderTitle} numberOfLines={1}>{item.title}</Text>
        <View style={styles.reminderMeta}>
          <Ionicons name="alert-circle" size={13} color={bgColor} />
          <Text style={styles.reminderMetaText}>
            Document your {isProblem ? 'learnings' : 'review'} — tap to create journal entry
          </Text>
        </View>
      </TouchableOpacity>
    );
  };

  const renderEntry = ({ item }: { item: JournalEntry }) => (
    <TouchableOpacity
      style={styles.entryCard}
      onPress={() => openDetailModal(item)}
      activeOpacity={0.7}
    >
      {/* Entry type color bar on left */}
      <View style={[
        styles.entryColorBar,
        { backgroundColor: item.entry_type === 'best_practice' ? '#10B981' : item.entry_type === 'learning' ? '#EF4444' : '#9CA3AF' }
      ]} />
      <View style={styles.entryContent}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle} numberOfLines={1}>{item.decision_title}</Text>
          <TouchableOpacity
            onPress={() => handleDelete(item.id)}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons name="trash-outline" size={16} color={COLORS.error} />
          </TouchableOpacity>
        </View>

        <View style={styles.badgeRow}>
          {getEntryTypeBadge(item.entry_type)}
          {getModuleBadge(item.linked_module)}
          {item.linked_title && (
            <Text style={styles.linkedTitleText} numberOfLines={1}>
              {item.linked_title}
            </Text>
          )}
        </View>

        {item.decision_description ? (
          <Text style={styles.description} numberOfLines={2}>{item.decision_description}</Text>
        ) : null}

        {item.outcome ? (
          <View style={styles.outcomeBox}>
            <Text style={styles.outcomeLabel}>Outcome:</Text>
            <Text style={styles.outcomeText} numberOfLines={2}>{item.outcome}</Text>
          </View>
        ) : null}

        {item.lessons_learned ? (
          <View style={styles.lessonBox}>
            <Ionicons name="bulb" size={13} color={COLORS.warning} />
            <Text style={styles.lessonText} numberOfLines={1}>{item.lessons_learned}</Text>
          </View>
        ) : null}

        <View style={styles.cardFooter}>
          <Text style={styles.cardDate}>{formatDate(item.decision_date || item.created_at)}</Text>
          <View style={[
            styles.statusDot,
            { backgroundColor: item.status === 'completed' ? '#10B981' : '#F59E0B' }
          ]} />
        </View>
      </View>
    </TouchableOpacity>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="book-outline" size={64} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No Journal Entries</Text>
      <Text style={styles.emptyText}>
        Document learnings from your decisions, goals, and tasks
      </Text>
      <TouchableOpacity style={styles.emptyButton} onPress={() => openCreateModal()}>
        <Ionicons name="add" size={20} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Add First Entry</Text>
      </TouchableOpacity>
    </View>
  );

  const filterOptions = [
    { key: 'all', label: 'All', icon: 'list' },
    { key: 'decision', label: 'Decisions', icon: 'compass' },
    { key: 'gem', label: 'GEM', icon: 'flag' },
    { key: 'ctt', label: 'CTT', icon: 'checkmark-circle' },
    { key: 'solution_finder', label: 'Finders', icon: 'search' },
    { key: 'lifestyle', label: 'Lifestyle', icon: 'leaf' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Learning Journal</Text>
          <Text style={styles.subtitle}>Best Practices & Learnings</Text>
        </View>
        <TouchableOpacity style={styles.addButton} onPress={() => openCreateModal()}>
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow} contentContainerStyle={styles.filterContent}>
        {filterOptions.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterChip, activeFilter === f.key && styles.filterChipActive]}
            onPress={() => setActiveFilter(f.key)}
          >
            <Ionicons name={f.icon as any} size={14} color={activeFilter === f.key ? COLORS.white : COLORS.textSecondary} />
            <Text style={[styles.filterChipText, activeFilter === f.key && styles.filterChipTextActive]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={entries}
        renderItem={renderEntry}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.list, { paddingBottom: 100 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListHeaderComponent={
          reminders.length > 0 ? (
            <View style={styles.remindersSection}>
              <View style={styles.remindersSectionHeader}>
                <Ionicons name="notifications" size={16} color="#EF4444" />
                <Text style={styles.remindersSectionTitle}>Review Reminders</Text>
                <View style={styles.reminderCountBadge}>
                  <Text style={styles.reminderCountText}>{reminders.length}</Text>
                </View>
              </View>
              <FlatList
                data={reminders}
                renderItem={renderReminderCard}
                keyExtractor={(item) => item.decision_id}
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.remindersScroll}
              />
            </View>
          ) : null
        }
        ListEmptyComponent={renderEmpty}
      />

      {/* ====== CREATE MODAL ====== */}
      <Modal visible={modalVisible} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setModalVisible(false)}>
        <SafeAreaView style={styles.modalContainer}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>New Journal Entry</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
              {/* Entry Type Selection */}
              <Text style={styles.sectionLabel}>Entry Type *</Text>
              <View style={styles.entryTypeRow}>
                {ENTRY_TYPES.map((t) => (
                  <TouchableOpacity
                    key={t.key}
                    style={[
                      styles.entryTypeCard,
                      formEntryType === t.key && { borderColor: t.color, backgroundColor: t.color + '10' },
                    ]}
                    onPress={() => setFormEntryType(t.key)}
                  >
                    <Ionicons name={t.icon as any} size={22} color={formEntryType === t.key ? t.color : COLORS.textMuted} />
                    <Text style={[styles.entryTypeLabel, formEntryType === t.key && { color: t.color }]}>{t.label}</Text>
                    <Text style={styles.entryTypeDesc}>{t.desc}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Link to Module */}
              <Text style={styles.sectionLabel}>Link to Module *</Text>
              <TouchableOpacity style={styles.pickerButton} onPress={() => { setShowModulePicker(true); fetchLinkableItems(); }}>
                {formLinkedModule ? (
                  <View style={styles.pickerSelected}>
                    <Ionicons name={MODULE_CONFIG[formLinkedModule]?.icon as any} size={16} color={MODULE_CONFIG[formLinkedModule]?.color} />
                    <Text style={[styles.pickerSelectedText, { color: MODULE_CONFIG[formLinkedModule]?.color }]}>
                      {MODULE_CONFIG[formLinkedModule]?.label}
                    </Text>
                  </View>
                ) : (
                  <Text style={styles.pickerPlaceholder}>Select module...</Text>
                )}
                <Ionicons name="chevron-down" size={18} color={COLORS.textMuted} />
              </TouchableOpacity>

              {/* Link to specific item */}
              {formLinkedModule && (
                <>
                  <Text style={styles.sectionLabel}>Link to Item (optional)</Text>
                  <TouchableOpacity style={styles.pickerButton} onPress={() => setShowItemPicker(true)}>
                    {formLinkedId ? (
                      <Text style={styles.pickerSelectedText} numberOfLines={1}>{formLinkedTitle || formLinkedId}</Text>
                    ) : (
                      <Text style={styles.pickerPlaceholder}>Select specific item...</Text>
                    )}
                    <Ionicons name="chevron-down" size={18} color={COLORS.textMuted} />
                  </TouchableOpacity>
                </>
              )}

              {/* Title */}
              <Text style={styles.sectionLabel}>Title *</Text>
              <TextInput
                style={styles.textInput}
                placeholder="What did you learn?"
                value={formTitle}
                onChangeText={setFormTitle}
                placeholderTextColor={COLORS.textMuted}
              />

              {/* Description */}
              <Text style={styles.sectionLabel}>Details</Text>
              <TextInput
                style={[styles.textInput, styles.textArea]}
                placeholder="Describe the outcome, what went well, what to improve..."
                value={formDescription}
                onChangeText={setFormDescription}
                multiline
                numberOfLines={5}
                textAlignVertical="top"
                placeholderTextColor={COLORS.textMuted}
              />

              <TouchableOpacity
                style={[styles.createBtn, (!formTitle.trim() || !formLinkedModule || !formEntryType) && styles.createBtnDisabled]}
                onPress={handleCreate}
                disabled={saving || !formTitle.trim() || !formLinkedModule || !formEntryType}
              >
                {saving ? (
                  <ActivityIndicator color={COLORS.white} size="small" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color={COLORS.white} />
                    <Text style={styles.createBtnText}>Create Entry</Text>
                  </>
                )}
              </TouchableOpacity>

              <View style={{ height: 40 }} />
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>

      {/* ====== MODULE PICKER MODAL ====== */}
      <Modal visible={showModulePicker} animationType="fade" transparent onRequestClose={() => setShowModulePicker(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowModulePicker(false)}>
          <View style={styles.pickerModal}>
            <Text style={styles.pickerModalTitle}>Select Module</Text>
            {Object.entries(MODULE_CONFIG).map(([key, config]) => (
              <TouchableOpacity
                key={key}
                style={[styles.pickerOption, formLinkedModule === key && { backgroundColor: config.color + '12' }]}
                onPress={() => {
                  setFormLinkedModule(key);
                  setFormLinkedId('');
                  setFormLinkedTitle('');
                  setShowModulePicker(false);
                }}
              >
                <Ionicons name={config.icon as any} size={20} color={config.color} />
                <Text style={[styles.pickerOptionText, formLinkedModule === key && { color: config.color, fontWeight: '600' }]}>{config.label}</Text>
                {formLinkedModule === key && <Ionicons name="checkmark" size={18} color={config.color} />}
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>

      {/* ====== ITEM PICKER MODAL ====== */}
      <Modal visible={showItemPicker} animationType="fade" transparent onRequestClose={() => setShowItemPicker(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowItemPicker(false)}>
          <View style={[styles.pickerModal, { maxHeight: 400 }]}>
            <Text style={styles.pickerModalTitle}>
              Select {MODULE_CONFIG[formLinkedModule]?.label || 'Item'}
            </Text>
            {loadingItems ? (
              <ActivityIndicator style={{ padding: 20 }} />
            ) : (
              <ScrollView style={{ maxHeight: 320 }}>
                <TouchableOpacity
                  style={styles.pickerOption}
                  onPress={() => { setFormLinkedId(''); setFormLinkedTitle(''); setShowItemPicker(false); }}
                >
                  <Ionicons name="remove-circle-outline" size={20} color={COLORS.textMuted} />
                  <Text style={styles.pickerOptionText}>No specific item</Text>
                </TouchableOpacity>
                {(linkableItems[formLinkedModule] || []).map((item) => (
                  <TouchableOpacity
                    key={item.id}
                    style={[styles.pickerOption, formLinkedId === item.id && { backgroundColor: COLORS.primary + '10' }]}
                    onPress={() => {
                      setFormLinkedId(item.id);
                      setFormLinkedTitle(item.title);
                      setShowItemPicker(false);
                    }}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.pickerOptionText} numberOfLines={1}>{item.title || 'Untitled'}</Text>
                      {item.extra ? <Text style={styles.pickerOptionExtra}>{item.extra}</Text> : null}
                    </View>
                    {formLinkedId === item.id && <Ionicons name="checkmark" size={18} color={COLORS.primary} />}
                  </TouchableOpacity>
                ))}
                {(linkableItems[formLinkedModule] || []).length === 0 && (
                  <Text style={styles.noItemsText}>No items found in this module</Text>
                )}
              </ScrollView>
            )}
          </View>
        </TouchableOpacity>
      </Modal>

      {/* ====== DETAIL / UPDATE MODAL ====== */}
      <Modal visible={detailModalVisible} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setDetailModalVisible(false)}>
        <SafeAreaView style={styles.modalContainer}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Journal Entry</Text>
              <TouchableOpacity onPress={() => setDetailModalVisible(false)}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            {selectedEntry && (
              <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
                {/* Entry info */}
                <Text style={styles.detailTitle}>{selectedEntry.decision_title}</Text>
                <View style={styles.badgeRow}>
                  {getEntryTypeBadge(selectedEntry.entry_type)}
                  {getModuleBadge(selectedEntry.linked_module)}
                </View>
                {selectedEntry.linked_title && (
                  <View style={styles.linkedInfoBox}>
                    <Ionicons name="link" size={14} color={COLORS.textSecondary} />
                    <Text style={styles.linkedInfoText}>{selectedEntry.linked_title}</Text>
                  </View>
                )}
                {selectedEntry.decision_description ? (
                  <Text style={styles.detailDesc}>{selectedEntry.decision_description}</Text>
                ) : null}

                {/* Outcome section */}
                <Text style={[styles.sectionLabel, { marginTop: 20 }]}>Outcome</Text>
                <TextInput
                  style={[styles.textInput, styles.textArea]}
                  placeholder="What was the result?"
                  value={editOutcome}
                  onChangeText={setEditOutcome}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                  placeholderTextColor={COLORS.textMuted}
                />

                {/* Rating */}
                <Text style={styles.sectionLabel}>Outcome Rating</Text>
                <View style={styles.ratingRow}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <TouchableOpacity key={star} onPress={() => setEditRating(star)} style={styles.starTouch}>
                      <Ionicons
                        name={star <= editRating ? 'star' : 'star-outline'}
                        size={28}
                        color={star <= editRating ? COLORS.warning : COLORS.textMuted}
                      />
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Lessons Learned */}
                <Text style={styles.sectionLabel}>Lessons Learned</Text>
                <TextInput
                  style={[styles.textInput, styles.textArea]}
                  placeholder="What would you do differently?"
                  value={editLessons}
                  onChangeText={setEditLessons}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                  placeholderTextColor={COLORS.textMuted}
                />

                {/* Failure Reasons (if Learning type) */}
                {selectedEntry.entry_type === 'learning' && (
                  <>
                    <Text style={styles.sectionLabel}>Root Causes</Text>
                    {FAILURE_REASONS.map((reason) => {
                      const isSelected = editFailureReasons.includes(reason);
                      return (
                        <TouchableOpacity
                          key={reason}
                          style={[styles.failureOption, isSelected && styles.failureOptionSelected]}
                          onPress={() => {
                            setEditFailureReasons(
                              isSelected
                                ? editFailureReasons.filter((r) => r !== reason)
                                : [...editFailureReasons, reason]
                            );
                          }}
                        >
                          <Ionicons
                            name={isSelected ? 'checkbox' : 'square-outline'}
                            size={20}
                            color={isSelected ? COLORS.error : COLORS.textMuted}
                          />
                          <Text style={[styles.failureOptionText, isSelected && { color: COLORS.error }]}>{reason}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </>
                )}

                {/* Status toggle */}
                <Text style={styles.sectionLabel}>Status</Text>
                <View style={styles.statusToggleRow}>
                  <TouchableOpacity
                    style={[styles.statusToggle, editStatus === 'pending' && styles.statusTogglePending]}
                    onPress={() => setEditStatus('pending')}
                  >
                    <Text style={[styles.statusToggleText, editStatus === 'pending' && { color: COLORS.warning }]}>Pending</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.statusToggle, editStatus === 'completed' && styles.statusToggleCompleted]}
                    onPress={() => setEditStatus('completed')}
                  >
                    <Text style={[styles.statusToggleText, editStatus === 'completed' && { color: COLORS.success }]}>Completed</Text>
                  </TouchableOpacity>
                </View>

                <TouchableOpacity style={styles.createBtn} onPress={handleUpdateEntry} disabled={updatingEntry}>
                  {updatingEntry ? (
                    <ActivityIndicator color={COLORS.white} size="small" />
                  ) : (
                    <>
                      <Ionicons name="save" size={20} color={COLORS.white} />
                      <Text style={styles.createBtnText}>Save Changes</Text>
                    </>
                  )}
                </TouchableOpacity>

                <View style={{ height: 40 }} />
              </ScrollView>
            )}
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 12,
  },
  title: { fontSize: 26, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 13, color: COLORS.textSecondary, marginTop: 2 },
  addButton: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: COLORS.teal, justifyContent: 'center', alignItems: 'center',
  },
  filterRow: { maxHeight: 44, marginBottom: 4 },
  filterContent: { paddingHorizontal: 16, gap: 8, alignItems: 'center' },
  filterChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20,
    backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border,
  },
  filterChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  filterChipText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
  filterChipTextActive: { color: COLORS.white },
  list: { padding: 16, paddingTop: 8, flexGrow: 1 },

  // Reminders
  remindersSection: { marginBottom: 16 },
  remindersSectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  remindersSectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  reminderCountBadge: {
    backgroundColor: '#EF4444', borderRadius: 10,
    minWidth: 20, height: 20, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 6,
  },
  reminderCountText: { color: COLORS.white, fontSize: 11, fontWeight: '700' },
  remindersScroll: { gap: 10 },
  reminderCard: {
    width: 280, backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderLeftWidth: 4, shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08, shadowRadius: 4, elevation: 2,
  },
  reminderHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  priorityPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  priorityPillText: { fontSize: 11, fontWeight: '700' },
  overdueText: { fontSize: 11, color: '#EF4444', fontWeight: '600' },
  reminderTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 6 },
  reminderMeta: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  reminderMetaText: { fontSize: 11, color: COLORS.textSecondary, flex: 1 },

  // Entry cards
  entryCard: {
    flexDirection: 'row', backgroundColor: COLORS.white, borderRadius: 12,
    marginBottom: 10, overflow: 'hidden',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 3, elevation: 1,
  },
  entryColorBar: { width: 4 },
  entryContent: { flex: 1, padding: 14 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, flex: 1, marginRight: 8 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6, alignItems: 'center' },
  typeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
  },
  typeBadgeText: { fontSize: 11, fontWeight: '600' },
  moduleBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6,
  },
  moduleBadgeText: { fontSize: 10, fontWeight: '600' },
  linkedTitleText: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic', flex: 1 },
  description: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginTop: 8 },
  outcomeBox: {
    backgroundColor: 'rgba(16, 185, 129, 0.05)', borderRadius: 8, padding: 10, marginTop: 8,
  },
  outcomeLabel: { fontSize: 11, color: COLORS.success, fontWeight: '600', marginBottom: 2 },
  outcomeText: { fontSize: 13, color: COLORS.textPrimary },
  lessonBox: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  lessonText: { fontSize: 12, color: COLORS.textSecondary, flex: 1, fontStyle: 'italic' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  cardDate: { fontSize: 11, color: COLORS.textMuted },
  statusDot: { width: 8, height: 8, borderRadius: 4 },

  // Empty state
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 64 },
  emptyTitle: { fontSize: 20, fontWeight: '600', color: COLORS.textPrimary, marginTop: 16 },
  emptyText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, marginBottom: 24, paddingHorizontal: 32 },
  emptyButton: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.teal,
    paddingVertical: 12, paddingHorizontal: 20, borderRadius: 12, gap: 8,
  },
  emptyButtonText: { fontSize: 16, fontWeight: '600', color: COLORS.white },

  // Modals
  modalContainer: { flex: 1, backgroundColor: COLORS.background },
  modalContent: { flex: 1, padding: 16 },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20,
  },
  modalTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary },

  // Form fields
  sectionLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 16, marginBottom: 8 },
  textInput: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: COLORS.textPrimary,
  },
  textArea: { minHeight: 80 },

  // Entry type cards
  entryTypeRow: { flexDirection: 'row', gap: 10 },
  entryTypeCard: {
    flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderWidth: 2, borderColor: COLORS.border, alignItems: 'center', gap: 6,
  },
  entryTypeLabel: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  entryTypeDesc: { fontSize: 10, color: COLORS.textSecondary, textAlign: 'center' },

  // Picker
  pickerButton: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 13,
  },
  pickerPlaceholder: { fontSize: 15, color: COLORS.textMuted },
  pickerSelected: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pickerSelectedText: { fontSize: 15, color: COLORS.textPrimary, fontWeight: '500' },

  // Picker modal
  overlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center', alignItems: 'center', padding: 32,
  },
  pickerModal: {
    backgroundColor: COLORS.white, borderRadius: 16, padding: 20, width: '100%', maxWidth: 360,
  },
  pickerModalTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  pickerOption: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 12, paddingHorizontal: 12, borderRadius: 10,
  },
  pickerOptionText: { fontSize: 15, color: COLORS.textPrimary, flex: 1 },
  pickerOptionExtra: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  noItemsText: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', padding: 20 },

  // Create button
  createBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: COLORS.teal, borderRadius: 12, paddingVertical: 15, marginTop: 24,
  },
  createBtnDisabled: { opacity: 0.5 },
  createBtnText: { fontSize: 16, fontWeight: '700', color: COLORS.white },

  // Detail modal
  detailTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary },
  detailDesc: { fontSize: 14, color: COLORS.textSecondary, lineHeight: 20, marginTop: 10 },
  linkedInfoBox: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 8, backgroundColor: COLORS.divider, borderRadius: 8, padding: 8,
  },
  linkedInfoText: { fontSize: 13, color: COLORS.textSecondary, flex: 1 },

  // Rating
  ratingRow: { flexDirection: 'row', gap: 8 },
  starTouch: { padding: 4 },

  // Failure reasons
  failureOption: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, marginBottom: 4,
    backgroundColor: COLORS.white,
  },
  failureOptionSelected: { backgroundColor: '#EF444410' },
  failureOptionText: { fontSize: 14, color: COLORS.textPrimary },

  // Status toggle
  statusToggleRow: { flexDirection: 'row', gap: 10 },
  statusToggle: {
    flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: 'center',
    borderWidth: 1.5, borderColor: COLORS.border,
  },
  statusTogglePending: { borderColor: COLORS.warning, backgroundColor: COLORS.warning + '10' },
  statusToggleCompleted: { borderColor: COLORS.success, backgroundColor: COLORS.success + '10' },
  statusToggleText: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary },
});
