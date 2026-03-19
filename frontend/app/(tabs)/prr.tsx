import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Platform,
  Modal,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';

interface Decision {
  id: string;
  title: string;
  context: string;
  status: string;
  options: any[];
  created_at: string;
  chosen_option_id?: string;
}

export default function PRRScreen() {
  const router = useRouter();
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const fetchDecisions = async () => {
    try {
      const response = await api.get('/decisions');
      setDecisions(response.data);
    } catch (error) {
      console.error('Error fetching decisions:', error);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchDecisions();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDecisions();
    setRefreshing(false);
  };

  const handleDeletePress = (id: string) => {
    setDeleteTargetId(id);
    setDeleteModalVisible(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTargetId) return;
    
    try {
      await api.delete(`/decisions/${deleteTargetId}`);
      setDecisions((prev) => prev.filter((d) => d.id !== deleteTargetId));
    } catch (error) {
      console.error('Delete error:', error);
    } finally {
      setDeleteModalVisible(false);
      setDeleteTargetId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalVisible(false);
    setDeleteTargetId(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return COLORS.success;
      case 'in_progress':
        return COLORS.warning;
      default:
        return COLORS.textMuted;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'in_progress':
        return 'In Progress';
      default:
        return 'Draft';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const renderDecision = ({ item }: { item: Decision }) => (
    <Card style={styles.decisionCard}>
      <TouchableOpacity
        onPress={() => router.push(`/prr/${item.id}`)}
        activeOpacity={0.7}
        style={styles.cardContent}
      >
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.title}
          </Text>
          <View style={styles.statusContainer}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: getStatusColor(item.status) },
              ]}
            />
            <Text style={styles.statusText}>{getStatusLabel(item.status)}</Text>
          </View>
        </View>
        <Text style={styles.cardContext} numberOfLines={2}>
          {item.context}
        </Text>
        <View style={styles.cardFooter}>
          <Text style={styles.cardDate}>{formatDate(item.created_at)}</Text>
          <View style={styles.optionsCount}>
            <Ionicons name="list" size={14} color={COLORS.textSecondary} />
            <Text style={styles.optionsText}>
              {item.options?.length || 0} options
            </Text>
          </View>
        </View>
      </TouchableOpacity>
      <TouchableOpacity
        onPress={() => handleDeletePress(item.id)}
        style={styles.deleteButton}
      >
        <Ionicons name="trash-outline" size={20} color={COLORS.error} />
      </TouchableOpacity>
    </Card>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="analytics-outline" size={64} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No PRR Decisions Yet</Text>
      <Text style={styles.emptyText}>
        Start making better decisions with the PRR system
      </Text>
      <TouchableOpacity
        style={styles.emptyButton}
        onPress={() => router.push('/prr/new')}
      >
        <Ionicons name="add" size={20} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Create First Decision</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Decision Box</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => router.push('/prr/new')}
        >
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={decisions}
        renderItem={renderDecision}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={renderEmpty}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        visible={deleteModalVisible}
        transparent={true}
        animationType="fade"
        onRequestClose={handleDeleteCancel}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Ionicons name="warning" size={48} color={COLORS.error} />
            <Text style={styles.modalTitle}>Delete Decision?</Text>
            <Text style={styles.modalText}>
              Are you sure you want to delete this decision? This action cannot be undone.
            </Text>
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelButton} onPress={handleDeleteCancel}>
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.confirmDeleteButton} onPress={handleDeleteConfirm}>
                <Text style={styles.confirmDeleteButtonText}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
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
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: 16,
    paddingTop: 0,
    flexGrow: 1,
  },
  decisionCard: {
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  cardContent: {
    flex: 1,
  },
  cardHeader: {
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  cardContext: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
    marginBottom: 12,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardDate: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  optionsCount: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  optionsText: {
    fontSize: 12,
    color: COLORS.textSecondary,
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
    backgroundColor: COLORS.primary,
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
  deleteButton: {
    padding: 12,
    marginLeft: 8,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: COLORS.white,
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    maxWidth: 320,
    width: '100%',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginTop: 16,
    marginBottom: 8,
  },
  modalText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  confirmDeleteButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: COLORS.error,
    alignItems: 'center',
  },
  confirmDeleteButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.white,
  },
});
