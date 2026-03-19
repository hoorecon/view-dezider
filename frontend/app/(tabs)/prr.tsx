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

  const handleDelete = async (id: string) => {
    const performDelete = async () => {
      try {
        console.log('Deleting decision:', id);
        await api.delete(`/decisions/${id}`);
        console.log('Delete successful');
        setDecisions((prev) => prev.filter((d) => d.id !== id));
      } catch (error) {
        console.error('Delete error:', error);
        if (Platform.OS === 'web' && typeof window !== 'undefined') {
          window.alert('Failed to delete decision');
        } else {
          Alert.alert('Error', 'Failed to delete decision');
        }
      }
    };

    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      // Use window.confirm for web
      const confirmed = window.confirm('Are you sure you want to delete this decision?');
      console.log('Confirm result:', confirmed);
      if (confirmed) {
        await performDelete();
      }
    } else {
      // Use Alert.alert for native
      Alert.alert(
        'Delete Decision',
        'Are you sure you want to delete this decision?',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Delete',
            style: 'destructive',
            onPress: performDelete,
          },
        ]
      );
    }
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
        onPress={() => handleDelete(item.id)}
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
});
