import React, { useState, useCallback } from 'react';
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
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

export default function SolutionMatrixListScreen() {
  const router = useRouter();
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchEntries = async () => {
    try {
      const res = await api.get('/solution-matrices');
      setEntries(res.data || []);
    } catch (e) {
      console.error('Error fetching solution matrices:', e);
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
    Alert.alert('Delete', 'Delete this entry?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/solution-matrices/${id}`);
            fetchEntries();
          } catch (e) {
            Alert.alert('Error', 'Failed to delete');
          }
        },
      },
    ]);
  };

  const getAreaName = (id: string) => {
    const areas: Record<string, string> = {
      career: 'Career', finance: 'Finance', relationships: 'Relationships',
      holistic_health: 'Holistic Health', assets: 'Assets',
      knowledge_skills: 'Knowledge & Skills', social_image: 'Social Image',
      social_contributions: 'Social Contributions',
      hobbies_entertainment: 'Hobbies', spirituality_religion: 'Spirituality',
    };
    return areas[id] || id;
  };

  const getSelectedCategories = (cat: Record<string, boolean>) => {
    return Object.entries(cat || {}).filter(([_, v]) => v).map(([k]) =>
      k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#E91E63', '#8E24AA']} style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Advanced Solution Matrix</Text>
        <TouchableOpacity
          style={styles.addHeaderBtn}
          onPress={() => router.push('/tools/solution-matrix')}
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
          <ActivityIndicator size="large" color={COLORS.accent} style={{ marginTop: 40 }} />
        ) : entries.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="grid" size={56} color={COLORS.textMuted} />
            <Text style={styles.emptyTitle}>No Solution Matrices Yet</Text>
            <Text style={styles.emptySubtitle}>Create an advanced matrix to analyze solutions across Self, Micro, and Macro layers</Text>
            <TouchableOpacity
              style={styles.emptyBtn}
              onPress={() => router.push('/tools/solution-matrix')}
            >
              <Text style={styles.emptyBtnText}>Create New</Text>
            </TouchableOpacity>
          </View>
        ) : (
          entries.map((entry) => {
            const cats = getSelectedCategories(entry.solution_category);
            return (
              <TouchableOpacity
                key={entry.entry_id}
                style={styles.card}
                onPress={() => router.push({ pathname: '/tools/solution-matrix', params: { id: entry.entry_id } })}
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
                {cats.length > 0 && (
                  <View style={styles.catRow}>
                    {cats.slice(0, 3).map(c => (
                      <View key={c} style={styles.catBadge}>
                        <Text style={styles.catBadgeText}>{c}</Text>
                      </View>
                    ))}
                  </View>
                )}
                <View style={styles.cardFooter}>
                  <Text style={styles.cardDate}>{new Date(entry.created_at).toLocaleDateString()}</Text>
                  <Text style={styles.cardActions}>
                    {(entry.action_items || []).length} actions
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
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: '#FFF' },
  addHeaderBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16 },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 16 },
  emptySubtitle: {
    fontSize: 14, color: COLORS.textSecondary, textAlign: 'center',
    marginTop: 8, paddingHorizontal: 32,
  },
  emptyBtn: {
    marginTop: 20, paddingHorizontal: 24, paddingVertical: 12,
    backgroundColor: COLORS.accent, borderRadius: 12,
  },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  card: {
    backgroundColor: COLORS.white, borderRadius: 14,
    padding: 16, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
    borderLeftWidth: 4, borderLeftColor: COLORS.accent,
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
    fontSize: 11, fontWeight: '600', color: COLORS.accent,
    textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4,
  },
  cardGoal: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8 },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  catBadge: {
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8,
    backgroundColor: 'rgba(99,102,241,0.1)',
  },
  catBadgeText: { fontSize: 10, fontWeight: '600', color: '#6366F1' },
  cardFooter: {
    flexDirection: 'row', justifyContent: 'space-between',
    borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 8,
  },
  cardDate: { fontSize: 12, color: COLORS.textMuted },
  cardActions: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
});
