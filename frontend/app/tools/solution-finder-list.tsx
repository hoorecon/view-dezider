import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { getLifeAreaName } from '../../src/constants/lifeAreas';

export default function SolutionFinderListScreen() {
  const router = useRouter();
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Robust back: pop history if we got here via in-app nav, else go to the
  // dashboard. Fixes the dead "back" button on direct/deep-linked loads
  // (e.g. opening /tools/solution-finder-list in a fresh tab) where
  // router.back() is a no-op because there is no history to pop.
  const goBack = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace('/(tabs)' as any);
  }, [router]);

  const fetchEntries = async () => {
    try {
      const res = await api.get('/solution-finders');
      setEntries(res.data || []);
    } catch (e) {
      console.error('Error fetching solution finders:', e);
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

  const handleDelete = (id: string) => {
    showAlert('Delete', 'Are you sure you want to delete this entry?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/solution-finders/${id}`);
            fetchEntries();
          } catch (e) {
            showAlert('Error', 'Failed to delete');
          }
        },
      },
    ]);
  };

  const getAreaName = (id: string) => getLifeAreaName(id, id);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.header} style={styles.header}>
        <TouchableOpacity onPress={goBack} style={styles.backBtn} accessibilityLabel="Back to dashboard">
          <Ionicons name="home" size={22} color="#FFFFFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Solution Finder</Text>
        <TouchableOpacity
          style={styles.addHeaderBtn}
          onPress={() => router.push('/tools/solution-finder')}
        >
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="search" size={56} color={COLORS.textMuted} />
            <Text style={styles.emptyTitle}>No Solution Finders Yet</Text>
            <Text style={styles.emptySubtitle}>Start your first structured problem-solving worksheet</Text>
            <TouchableOpacity
              style={styles.emptyBtn}
              onPress={() => router.push('/tools/solution-finder')}
            >
              <Text style={styles.emptyBtnText}>Create New</Text>
            </TouchableOpacity>
          </View>
        ) : (
          entries.map((entry) => (
            <TouchableOpacity
              key={entry.entry_id}
              style={styles.card}
              onPress={() => router.push({ pathname: '/tools/solution-finder', params: { id: entry.entry_id } })}
            >
              <View style={styles.cardHeader}>
                <View style={[
                  styles.statusBadge,
                  entry.status === 'completed' && styles.statusCompleted
                ]}>
                  <Text style={[
                    styles.statusText,
                    entry.status === 'completed' && styles.statusTextCompleted
                  ]}>
                    {entry.status === 'completed' ? 'COMPLETED' : 'IN PROGRESS'}
                  </Text>
                </View>
                <TouchableOpacity onPress={() => handleDelete(entry.entry_id)}>
                  <Ionicons name="trash-outline" size={18} color={COLORS.error} />
                </TouchableOpacity>
              </View>
              <Text style={styles.cardArea}>{getAreaName(entry.area_of_life)}</Text>
              <Text style={styles.cardGoal} numberOfLines={2}>{entry.smart_goal || 'No goal set'}</Text>
              <View style={styles.cardFooter}>
                <Text style={styles.cardDate}>
                  {(() => {
                    const raw = entry.updated_at || entry.created_at;
                    if (!raw) return '';
                    const d = new Date(raw);
                    if (isNaN(d.getTime())) return '';
                    return d.toLocaleString(undefined, {
                      year: 'numeric', month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                    });
                  })()}
                </Text>
                <Text style={styles.cardActions}>
                  {(entry.action_items || []).length} action items
                </Text>
              </View>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingBottom: 20,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
    marginRight: 12,
  },
  headerTitle: {
    flex: 1, fontSize: 18, fontWeight: '700', color: '#FFF',
  },
  addHeaderBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16 },
  emptyState: {
    alignItems: 'center', paddingTop: 60,
  },
  emptyTitle: {
    fontSize: 18, fontWeight: '700', color: COLORS.textPrimary,
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14, color: COLORS.textSecondary, textAlign: 'center',
    marginTop: 8, paddingHorizontal: 32,
  },
  emptyBtn: {
    marginTop: 20, paddingHorizontal: 24, paddingVertical: 12,
    backgroundColor: COLORS.primary, borderRadius: 12,
  },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  card: {
    backgroundColor: COLORS.white, borderRadius: 14,
    padding: 16, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  cardHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  statusBadge: {
    paddingHorizontal: 10, paddingVertical: 3,
    borderRadius: 10, backgroundColor: 'rgba(245,158,11,0.1)',
  },
  statusCompleted: { backgroundColor: 'rgba(16,185,129,0.1)' },
  statusText: { fontSize: 10, fontWeight: '700', color: '#F59E0B' },
  statusTextCompleted: { color: '#10B981' },
  cardArea: {
    fontSize: 11, fontWeight: '600', color: COLORS.primary,
    textTransform: 'uppercase', letterSpacing: 1,
    marginBottom: 4,
  },
  cardGoal: {
    fontSize: 15, fontWeight: '600', color: COLORS.textPrimary,
    marginBottom: 10,
  },
  cardFooter: {
    flexDirection: 'row', justifyContent: 'space-between',
    borderTopWidth: 1, borderTopColor: COLORS.divider,
    paddingTop: 8,
  },
  cardDate: { fontSize: 12, color: COLORS.textMuted },
  cardActions: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
});
