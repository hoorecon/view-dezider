import React, { useState, useCallback } from 'react';
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
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';

interface JournalEntry {
  id: string;
  decision_title: string;
  decision_description: string;
  outcome: string;
  outcome_rating: number;
  lessons_learned: string;
  failure_reasons: string[];
  status: string;
  decision_date: string;
  created_at: string;
}

const FAILURE_REASONS = [
  'Missed important factors',
  'Underestimated factor importance',
  'Unrealistic assessment',
  'Insufficient options considered',
  'Delayed implementation',
];

export default function JournalScreen() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);
  const [newEntry, setNewEntry] = useState({
    decision_title: '',
    decision_description: '',
  });
  const [saving, setSaving] = useState(false);

  const fetchEntries = async () => {
    try {
      const response = await api.get('/journal');
      setEntries(response.data);
    } catch (error) {
      console.error('Error fetching entries:', error);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchEntries();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchEntries();
    setRefreshing(false);
  };

  const handleCreate = async () => {
    if (!newEntry.decision_title || !newEntry.decision_description) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setSaving(true);
    try {
      await api.post('/journal', newEntry);
      setModalVisible(false);
      setNewEntry({ decision_title: '', decision_description: '' });
      fetchEntries();
    } catch (error) {
      Alert.alert('Error', 'Failed to create entry');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    Alert.alert(
      'Delete Entry',
      'Are you sure you want to delete this journal entry?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/journal/${id}`);
              setEntries(entries.filter((e) => e.id !== id));
            } catch (error) {
              Alert.alert('Error', 'Failed to delete entry');
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const renderStars = (rating: number) => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Ionicons
            key={star}
            name={star <= rating ? 'star' : 'star-outline'}
            size={14}
            color={star <= rating ? COLORS.warning : COLORS.textMuted}
          />
        ))}
      </View>
    );
  };

  const renderEntry = ({ item }: { item: JournalEntry }) => (
    <Card style={styles.entryCard}>
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleRow}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.decision_title}
          </Text>
          <TouchableOpacity
            onPress={() => handleDelete(item.id)}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
          </TouchableOpacity>
        </View>
        <View style={styles.statusRow}>
          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  item.status === 'completed'
                    ? 'rgba(16, 185, 129, 0.1)'
                    : 'rgba(245, 158, 11, 0.1)',
              },
            ]}
          >
            <Text
              style={[
                styles.statusText,
                {
                  color:
                    item.status === 'completed' ? COLORS.success : COLORS.warning,
                },
              ]}
            >
              {item.status === 'completed' ? 'Reviewed' : 'Pending Review'}
            </Text>
          </View>
          {item.outcome_rating > 0 && renderStars(item.outcome_rating)}
        </View>
      </View>

      <Text style={styles.description} numberOfLines={2}>
        {item.decision_description}
      </Text>

      {item.outcome ? (
        <View style={styles.outcomeBox}>
          <Text style={styles.outcomeLabel}>Outcome:</Text>
          <Text style={styles.outcomeText} numberOfLines={2}>
            {item.outcome}
          </Text>
        </View>
      ) : null}

      {item.lessons_learned ? (
        <View style={styles.lessonBox}>
          <Ionicons name="bulb" size={14} color={COLORS.warning} />
          <Text style={styles.lessonText} numberOfLines={1}>
            {item.lessons_learned}
          </Text>
        </View>
      ) : null}

      <Text style={styles.cardDate}>{formatDate(item.decision_date)}</Text>
    </Card>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="book-outline" size={64} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No Journal Entries</Text>
      <Text style={styles.emptyText}>
        Record your decisions and learn from outcomes
      </Text>
      <TouchableOpacity
        style={styles.emptyButton}
        onPress={() => setModalVisible(true)}
      >
        <Ionicons name="add" size={20} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Add First Entry</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Decision Journal</Text>
          <Text style={styles.subtitle}>Learn from your decisions</Text>
        </View>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setModalVisible(true)}
        >
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={entries}
        renderItem={renderEntry}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={renderEmpty}
      />

      {/* Create Entry Modal */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setModalVisible(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.modalContent}
          >
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>New Journal Entry</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <Input
                label="Decision Title"
                placeholder="What decision did you make?"
                value={newEntry.decision_title}
                onChangeText={(text) =>
                  setNewEntry({ ...newEntry, decision_title: text })
                }
              />

              <Input
                label="Description"
                placeholder="Describe the decision and context..."
                value={newEntry.decision_description}
                onChangeText={(text) =>
                  setNewEntry({ ...newEntry, decision_description: text })
                }
                multiline
                numberOfLines={4}
              />

              <Text style={styles.tipText}>
                Tip: Come back later to record the outcome and lessons learned
              </Text>

              <GradientButton
                title="Create Entry"
                onPress={handleCreate}
                loading={saving}
                style={styles.createButton}
              />
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    paddingTop: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: 16,
    paddingTop: 0,
    flexGrow: 1,
  },
  entryCard: {
    marginBottom: 12,
  },
  cardHeader: {
    marginBottom: 8,
  },
  cardTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  starsContainer: {
    flexDirection: 'row',
    gap: 2,
  },
  description: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
    marginBottom: 8,
  },
  outcomeBox: {
    backgroundColor: 'rgba(16, 185, 129, 0.05)',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  outcomeLabel: {
    fontSize: 11,
    color: COLORS.success,
    fontWeight: '600',
    marginBottom: 2,
  },
  outcomeText: {
    fontSize: 13,
    color: COLORS.textPrimary,
  },
  lessonBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  lessonText: {
    fontSize: 12,
    color: COLORS.textSecondary,
    flex: 1,
    fontStyle: 'italic',
  },
  cardDate: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 24,
  },
  emptyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.teal,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    gap: 8,
  },
  emptyButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.white,
  },
  modalContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  tipText: {
    fontSize: 13,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
    marginBottom: 24,
  },
  createButton: {
    marginBottom: 32,
  },
});
