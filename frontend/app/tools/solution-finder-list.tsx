import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { getLifeAreaName } from '../../src/constants/lifeAreas';
import { safeBack } from '../../src/utils/navigation';
import LoadErrorState from '../../src/components/LoadErrorState';

import PaywallGate from '../../src/components/PaywallGate';
import { useAuthStore } from '../../src/store/authStore';
import { isAdminRole } from '../../src/constants/adminTheme';

export default function SolutionFinderListScreen() {
  const router = useRouter();
  const user = useAuthStore(s => s.user);
  const isAdmin = isAdminRole(user?.role) || Boolean(user?.is_admin);
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [showSamples, setShowSamples] = useState(true);

  const goBack = useCallback(() => {
    if (router.canGoBack()) safeBack(router);
    else router.replace('/(tabs)' as any);
  }, [router]);

  const fetchEntries = async (samplesEnabled = showSamples) => {
    try {
      const shouldIncludeSamples = !isAdmin && samplesEnabled;
      const res = await api.get(`/solution-finders?include_samples=${shouldIncludeSamples}`);
      const all: any[] = res.data || [];
      const filtered = isAdmin ? all.filter(e => !e.is_sample) : all;
      setEntries(filtered);
      setLoadError(false);
    } catch (e) {
      console.error('Error fetching solution finders:', e);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSamples = (val: boolean) => {
    setShowSamples(val);
    setLoading(true);
    fetchEntries(val);
  };

  const retryFetch = () => {
    setLoading(true);
    setLoadError(false);
    fetchEntries();
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

  const getStatus = (entry: any) => {
    if (entry.status === 'completed') {
      return { label: 'COMPLETED', badgeStyle: styles.statusCompleted, textStyle: styles.statusTextCompleted };
    }
    if (entry.status === 'in_progress') {
      return { label: 'IN PROGRESS', badgeStyle: styles.statusInProgress, textStyle: styles.statusTextInProgress };
    }
    return { label: 'DRAFT', badgeStyle: styles.statusDraft, textStyle: styles.statusTextDraft };
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.header} style={styles.header}>
        <TouchableOpacity onPress={goBack} style={styles.backBtn} accessibilityLabel="Back to dashboard">
          <Ionicons name="home" size={22} color="#FFFFFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Solution Finder</Text>
        <PaywallGate module="solution_finder" onAllowed={() => router.push('/tools/solution-finder')}>
          <TouchableOpacity style={styles.addHeaderBtn} accessibilityLabel="Create new Solution Finder">
            <Ionicons name="add" size={24} color="#FFF" />
          </TouchableOpacity>
        </PaywallGate>
      </LinearGradient>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Sample Records Toggle Switch - hidden for admin */}
        {!isAdmin && (
          <View style={styles.sampleToggleRow}>
            <View style={styles.sampleToggleLeft}>
              <Ionicons name="sparkles-outline" size={16} color={COLORS.primary} />
              <Text style={styles.sampleToggleText}>Show Sample Records</Text>
            </View>
            <Switch
              value={showSamples}
              onValueChange={handleToggleSamples}
              trackColor={{ false: '#E5E7EB', true: '#C7D2FE' }}
              thumbColor={showSamples ? COLORS.primary : '#9CA3AF'}
            />
          </View>
        )}

        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : loadError && entries.length === 0 ? (
          <LoadErrorState onRetry={retryFetch} />
        ) : entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="search" size={56} color={COLORS.textMuted} />
            <Text style={styles.emptyTitle}>No Solution Finders Yet</Text>
            <Text style={styles.emptySubtitle}>Start your first structured problem-solving worksheet</Text>
            <PaywallGate module="solution_finder" onAllowed={() => router.push('/tools/solution-finder')}>
              <TouchableOpacity style={styles.emptyBtn}>
                <Text style={styles.emptyBtnText}>Create New</Text>
              </TouchableOpacity>
            </PaywallGate>
          </View>
        ) : (
          entries.map((entry) => {
            const st = getStatus(entry);
            return (
              <TouchableOpacity
                key={entry.entry_id}
                style={styles.card}
                onPress={() => router.push({ pathname: '/tools/solution-finder', params: { id: entry.entry_id } })}
              >
                <View style={styles.cardHeader}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    {entry.is_sample ? (
                      <View style={styles.sampleBadge}>
                        <Text style={styles.sampleBadgeText}>SAMPLE</Text>
                      </View>
                    ) : null}
                    <View style={[styles.statusBadge, st.badgeStyle]}>
                      <Text style={[styles.statusText, st.textStyle]}>
                        {st.label}
                      </Text>
                    </View>
                  </View>
                  {!entry.is_sample ? (
                    <TouchableOpacity onPress={() => handleDelete(entry.entry_id)}>
                      <Ionicons name="trash-outline" size={18} color={COLORS.error} />
                    </TouchableOpacity>
                  ) : null}
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
            );
          })
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
  sampleToggleRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#FFF', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10,
    marginBottom: 16, borderWidth: 1, borderColor: COLORS.border,
  },
  sampleToggleLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sampleToggleText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  sampleBadge: {
    backgroundColor: 'rgba(124,58,237,0.1)', paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 6, borderWidth: 1, borderColor: 'rgba(124,58,237,0.3)', marginRight: 6,
  },
  sampleBadgeText: { fontSize: 10, fontWeight: '700', color: COLORS.primary },
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
  statusInProgress: { backgroundColor: 'rgba(245,158,11,0.1)' },
  statusDraft: { backgroundColor: 'rgba(107,114,128,0.1)' },
  statusText: { fontSize: 10, fontWeight: '700', color: '#F59E0B' },
  statusTextCompleted: { color: '#10B981' },
  statusTextInProgress: { color: '#F59E0B' },
  statusTextDraft: { color: '#6B7280' },
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
