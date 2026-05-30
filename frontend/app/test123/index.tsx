/**
 * Test123 — Instant Decision history screen.
 * Accessible from the Dashboard's Test123 module card (NOT a bottom tab anymore).
 *
 * Features:
 *  - Prominent "Start Test123" CTA button (instant access)
 *  - List of past Test123 sessions with status
 *  - Per-row delete (trash icon)
 *  - Pull-to-refresh
 *  - "How Test123 Works" infographic
 */
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
import { LinearGradient } from 'expo-linear-gradient';
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

export default function Test123ListScreen() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Test123Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  const doDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await api.delete(`/test123/${id}`);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (e: any) {
      Alert.alert('Delete failed', e?.response?.data?.detail || 'Could not delete session');
    } finally {
      setDeletingId(null);
    }
  };

  const confirmDelete = (item: Test123Session) => {
    const msg = `Delete "${(item.situation || 'this session').slice(0, 60)}"? This cannot be undone.`;
    if (Platform.OS === 'web') {
      // eslint-disable-next-line no-alert
      if (window.confirm(msg)) doDelete(item.id);
      return;
    }
    Alert.alert('Delete Test123', msg, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => doDelete(item.id) },
    ]);
  };

  const renderSession = ({ item }: { item: Test123Session }) => (
    <View style={styles.sessionWrap}>
      <TouchableOpacity
        onPress={() => router.push(`/test123/${item.id}` as any)}
        activeOpacity={0.7}
        style={{ flex: 1 }}
      >
        <Card style={styles.sessionCard}>
          <View style={styles.cardHeader}>
            <Ionicons name="flash" size={22} color={COLORS.accent} />
            <View style={styles.testBadge}>
              <View style={[styles.testDot, { backgroundColor: getTestColor(item.completed_test) }]} />
              <Text style={styles.testText}>{getTestLabel(item.completed_test)}</Text>
            </View>
          </View>
          <Text style={styles.situation} numberOfLines={2}>{item.situation}</Text>
          {item.final_decision ? (
            <View style={styles.decisionBox}>
              <Text style={styles.decisionLabel}>Decision:</Text>
              <Text style={styles.decisionText} numberOfLines={1}>{item.final_decision}</Text>
            </View>
          ) : null}
          <Text style={styles.cardDate}>{formatDate(item.created_at)}</Text>
        </Card>
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.deleteBtn}
        onPress={() => confirmDelete(item)}
        disabled={deletingId === item.id}
        accessibilityLabel={`Delete ${item.situation}`}
      >
        <Ionicons
          name={deletingId === item.id ? 'hourglass' : 'trash-outline'}
          size={20}
          color={COLORS.error}
        />
      </TouchableOpacity>
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="flash-outline" size={64} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No Quick Decisions Yet</Text>
      <Text style={styles.emptyText}>Use Test123 for urgent decisions when you need to act fast.</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header with visible Back button */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Test123</Text>
          <Text style={styles.subtitle}>Instant Decision Making</Text>
        </View>
        <TouchableOpacity
          style={styles.homeBtn}
          onPress={() => router.push('/(tabs)/' as any)}
          accessibilityLabel="Home"
        >
          <Ionicons name="home" size={20} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      {/* BIG "Start Test123" CTA — clearly visible (no hidden + symbol) */}
      <TouchableOpacity
        style={styles.startBtnWrap}
        onPress={() => router.push('/test123/new' as any)}
        activeOpacity={0.85}
      >
        <LinearGradient
          colors={[COLORS.accent, COLORS.accentDark || '#7C3AED']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.startBtn}
        >
          <Ionicons name="flash" size={26} color="#FFF" />
          <View style={{ flex: 1 }}>
            <Text style={styles.startBtnTitle}>Start Test123</Text>
            <Text style={styles.startBtnSub}>For instant decisions when emotions cloud judgment</Text>
          </View>
          <Ionicons name="arrow-forward" size={22} color="#FFF" />
        </LinearGradient>
      </TouchableOpacity>

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
          <Ionicons name="arrow-forward" size={14} color={COLORS.textMuted} />
          <View style={styles.infoStep}>
            <View style={[styles.stepCircle, { backgroundColor: COLORS.warning }]}>
              <Text style={styles.stepNum}>2</Text>
            </View>
            <Text style={styles.stepLabel}>Worst case?</Text>
          </View>
          <Ionicons name="arrow-forward" size={14} color={COLORS.textMuted} />
          <View style={styles.infoStep}>
            <View style={[styles.stepCircle, { backgroundColor: COLORS.success }]}>
              <Text style={styles.stepNum}>3</Text>
            </View>
            <Text style={styles.stepLabel}>Core needs</Text>
          </View>
        </View>
      </Card>

      <Text style={styles.sectionLabel}>Past Sessions ({sessions.length})</Text>

      <FlatList
        data={sessions}
        renderItem={renderSession}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.list, { paddingBottom: 100 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={!loading ? renderEmpty : null}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 12, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: '#F1F5F9',
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: '#F1F5F9', justifyContent: 'center', alignItems: 'center',
  },
  homeBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: COLORS.accent, justifyContent: 'center', alignItems: 'center',
  },
  title: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textSecondary, marginTop: 1 },

  startBtnWrap: { margin: 16, marginBottom: 8, borderRadius: 16, overflow: 'hidden' },
  startBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 18, paddingVertical: 18, borderRadius: 16,
  },
  startBtnTitle: { color: '#FFF', fontSize: 18, fontWeight: '800' },
  startBtnSub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },

  infoCard: { marginHorizontal: 16, marginBottom: 14, padding: 14 },
  infoTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10, textAlign: 'center' },
  infoSteps: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6 },
  infoStep: { alignItems: 'center' },
  stepCircle: { width: 30, height: 30, borderRadius: 15, justifyContent: 'center', alignItems: 'center' },
  stepNum: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  stepLabel: { fontSize: 10, color: COLORS.textSecondary, marginTop: 4, maxWidth: 80, textAlign: 'center' },

  sectionLabel: {
    fontSize: 12, fontWeight: '700', color: COLORS.textMuted,
    paddingHorizontal: 20, paddingTop: 4, paddingBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4,
  },

  list: { paddingHorizontal: 16, gap: 8 },
  sessionWrap: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  sessionCard: { padding: 12 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  testBadge: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  testDot: { width: 8, height: 8, borderRadius: 4 },
  testText: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  situation: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 6 },
  decisionBox: { backgroundColor: '#F8FAFC', padding: 8, borderRadius: 6, marginBottom: 6 },
  decisionLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  decisionText: { fontSize: 12, color: COLORS.success, fontWeight: '700', marginTop: 2 },
  cardDate: { fontSize: 10, color: COLORS.textMuted },

  deleteBtn: {
    width: 40, height: 40, borderRadius: 10,
    backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA',
    justifyContent: 'center', alignItems: 'center',
  },

  emptyContainer: { alignItems: 'center', padding: 32, marginTop: 20 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  emptyText: { fontSize: 12, color: COLORS.textMuted, textAlign: 'center', marginTop: 4 },
});
