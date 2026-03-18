import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';

interface Test123Session {
  id: string;
  situation: string;
  completed_test: number;
  final_decision: string;
  created_at: string;
}

export default function Test123Screen() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Test123Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSessions = async () => {
    try {
      const response = await api.get('/test123');
      setSessions(response.data);
    } catch (error) {
      console.error('Error fetching sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchSessions();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchSessions();
    setRefreshing(false);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getTestLabel = (testNum: number) => {
    if (testNum === 0) return 'Not Started';
    if (testNum === 1) return 'Test 1 Complete';
    if (testNum === 2) return 'Test 2 Complete';
    return 'All Tests Complete';
  };

  const getTestColor = (testNum: number) => {
    if (testNum === 0) return COLORS.textMuted;
    if (testNum < 3) return COLORS.warning;
    return COLORS.success;
  };

  const renderSession = ({ item }: { item: Test123Session }) => (
    <TouchableOpacity
      onPress={() => router.push(`/test123/${item.id}`)}
      activeOpacity={0.7}
    >
      <Card style={styles.sessionCard}>
        <View style={styles.cardHeader}>
          <Ionicons name="flash" size={24} color={COLORS.accent} />
          <View style={styles.testBadge}>
            <View
              style={[
                styles.testDot,
                { backgroundColor: getTestColor(item.completed_test) },
              ]}
            />
            <Text style={styles.testText}>{getTestLabel(item.completed_test)}</Text>
          </View>
        </View>
        <Text style={styles.situation} numberOfLines={2}>
          {item.situation}
        </Text>
        {item.final_decision ? (
          <View style={styles.decisionBox}>
            <Text style={styles.decisionLabel}>Decision:</Text>
            <Text style={styles.decisionText} numberOfLines={1}>
              {item.final_decision}
            </Text>
          </View>
        ) : null}
        <Text style={styles.cardDate}>{formatDate(item.created_at)}</Text>
      </Card>
    </TouchableOpacity>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="flash-outline" size={64} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No Quick Decisions Yet</Text>
      <Text style={styles.emptyText}>
        Use Test123 for urgent decisions when you need to act fast
      </Text>
      <TouchableOpacity
        style={styles.emptyButton}
        onPress={() => router.push('/test123/new')}
      >
        <Ionicons name="flash" size={20} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Start Test123</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Test123</Text>
          <Text style={styles.subtitle}>Instant Decision Making</Text>
        </View>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => router.push('/test123/new')}
        >
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      {/* How it works */}
      <Card style={styles.infoCard}>
        <Text style={styles.infoTitle}>How Test123 Works</Text>
        <View style={styles.infoSteps}>
          <View style={styles.infoStep}>
            <View style={[styles.stepCircle, { backgroundColor: COLORS.accent }]}>
              <Text style={styles.stepNum}>1</Text>
            </View>
            <Text style={styles.stepLabel}>Am I emotional?</Text>
          </View>
          <View style={styles.stepArrow}>
            <Ionicons name="arrow-forward" size={16} color={COLORS.textMuted} />
          </View>
          <View style={styles.infoStep}>
            <View style={[styles.stepCircle, { backgroundColor: COLORS.warning }]}>
              <Text style={styles.stepNum}>2</Text>
            </View>
            <Text style={styles.stepLabel}>Worst case?</Text>
          </View>
          <View style={styles.stepArrow}>
            <Ionicons name="arrow-forward" size={16} color={COLORS.textMuted} />
          </View>
          <View style={styles.infoStep}>
            <View style={[styles.stepCircle, { backgroundColor: COLORS.success }]}>
              <Text style={styles.stepNum}>3</Text>
            </View>
            <Text style={styles.stepLabel}>Core needs</Text>
          </View>
        </View>
      </Card>

      <FlatList
        data={sessions}
        renderItem={renderSession}
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
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  infoCard: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 12,
    textAlign: 'center',
  },
  infoSteps: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  infoStep: {
    alignItems: 'center',
  },
  stepCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  stepNum: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  stepLabel: {
    fontSize: 11,
    color: COLORS.textSecondary,
  },
  stepArrow: {
    marginHorizontal: 12,
    marginBottom: 16,
  },
  list: {
    padding: 16,
    paddingTop: 0,
    flexGrow: 1,
  },
  sessionCard: {
    marginBottom: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  testBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  testDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  testText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  situation: {
    fontSize: 16,
    fontWeight: '500',
    color: COLORS.textPrimary,
    lineHeight: 22,
    marginBottom: 8,
  },
  decisionBox: {
    backgroundColor: COLORS.background,
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  decisionLabel: {
    fontSize: 11,
    color: COLORS.textSecondary,
    marginBottom: 2,
  },
  decisionText: {
    fontSize: 13,
    fontWeight: '500',
    color: COLORS.success,
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
    paddingHorizontal: 32,
  },
  emptyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.accent,
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
});
